//───────────────────────────────────────────────────────────────────────
// EventDetector.cpp — Core detection logic for all race events.
//───────────────────────────────────────────────────────────────────────
#include "EventDetector.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>

// ── Reset ─────────────────────────────────────────────────────────

void EventDetector::Reset()
{
    m_session = SessionData{};
    m_session.pluginVersion = "1.0.0";
    m_vehicles.clear();
    m_globalBestLapTime    = -1.0;
    m_raceStartET          = 0.0;
    m_headerCaptured       = false;
    m_racePhaseDetected    = false;
    m_lastScoring          = {};
    m_recentOvertakes.clear();
}

// ── Helpers ───────────────────────────────────────────────────────

std::string EventDetector::FormatHMS(double elapsedTime) const
{
    double relTime = elapsedTime - m_raceStartET;
    if (relTime < 0.0) relTime = 0.0;

    int totalSec = static_cast<int>(relTime);
    int h = totalSec / 3600;
    int m = (totalSec % 3600) / 60;
    int s = totalSec % 60;

    char buf[16];
    std::snprintf(buf, sizeof(buf), "%02d:%02d:%02d", h, m, s);
    return buf;
}

std::string EventDetector::FormatLapTimeHMS(double lapTime) const
{
    if (lapTime <= 0.0) return "00:00:00";

    int totalSec = static_cast<int>(lapTime);
    int m = totalSec / 60;
    int s = totalSec % 60;
    int ms = static_cast<int>((lapTime - totalSec) * 1000.0);

    char buf[16];
    std::snprintf(buf, sizeof(buf), "%02d:%02d.%03d", m, s, ms);
    return buf;
}

VehicleState& EventDetector::GetOrCreateVehicle(long id, const char* name)
{
    auto it = m_vehicles.find(id);
    if (it == m_vehicles.end())
    {
        VehicleState vs;
        vs.id   = id;
        vs.name = name ? name : "";
        m_vehicles[id] = vs;
        return m_vehicles[id];
    }
    // Update name if changed (e.g. multiplayer reconnect)
    if (name && it->second.name.empty())
        it->second.name = name;
    return it->second;
}

double EventDetector::Distance(const Vec3& a, const Vec3& b) const
{
    double dx = a.x - b.x;
    double dy = a.y - b.y;
    double dz = a.z - b.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

int EventDetector::EstimateLap(double /*et*/) const
{
    // We'll use the scoring data for the lap number when available.
    // This is a fallback — returns 0 if unknown.
    return 0;
}

std::vector<DriverSnapshot> EventDetector::TakeSnapshot() const
{
    std::vector<DriverSnapshot> snap;
    snap.reserve(m_lastScoring.vehicles.size());
    for (const auto& v : m_lastScoring.vehicles)
    {
        snap.push_back({v.name, v.place, v.pos, v.lapDist, v.lap});
    }
    return snap;
}

void EventDetector::AddEvent(RaceEvent&& ev)
{
    m_session.events.push_back(std::move(ev));
}

// ── ProcessScoring (≈5 Hz) ────────────────────────────────────────

void EventDetector::ProcessScoring(const ScoringInfoV01& info)
{
    // Capture session header once
    if (!m_headerCaptured)
    {
        m_session.trackName   = info.mTrackName;
        m_session.trackLength = info.mLapDist;
        m_session.numLaps     = info.mMaxLaps;

        // Determine session type
        if (info.mSession >= 10)
            m_session.sessionType = "race";
        else if (info.mSession >= 5)
            m_session.sessionType = "qualifying";
        else if (info.mSession >= 1)
            m_session.sessionType = "practice";
        else
            m_session.sessionType = "test_day";

        // Capture driver list with grid positions
        m_session.drivers.clear();
        for (long i = 0; i < info.mNumVehicles; ++i)
        {
            const auto& v = info.mVehicle[i];
            DriverInfo di;
            di.id      = v.mID;
            di.name    = v.mDriverName;
            di.vehicle = v.mVehicleName;
            di.gridPos = v.mPlace;
            m_session.drivers.push_back(di);
        }

        m_headerCaptured = true;
    }

    // Detect green flag for race start timestamp
    if (!m_racePhaseDetected && info.mGamePhase >= 5)
    {
        m_raceStartET = info.mCurrentET;
        m_session.raceStartET = m_raceStartET;
        m_racePhaseDetected = true;
    }

    // Update scoring snapshot for telemetry use
    m_lastScoring.currentET = info.mCurrentET;
    m_lastScoring.vehicles.clear();
    m_lastScoring.vehicles.reserve(info.mNumVehicles);

    for (long i = 0; i < info.mNumVehicles; ++i)
    {
        const auto& v = info.mVehicle[i];
        ScoringSnapshot::Entry e;
        e.id      = v.mID;
        e.name    = v.mDriverName;
        e.pos     = {v.mPos.x, v.mPos.y, v.mPos.z};
        e.lapDist = v.mLapDist;
        e.lap     = v.mTotalLaps;
        e.place   = v.mPlace;
        m_lastScoring.vehicles.push_back(e);

        // Initialize vehicle state
        GetOrCreateVehicle(v.mID, v.mDriverName);
    }

    // Run all scoring-based detectors (only during green flag or later)
    if (info.mGamePhase >= 5)
    {
        DetectOvertakes(info);
        DetectPenalties(info);
        DetectPitStops(info);
        DetectFastestLap(info);
        DetectProximity(info);
    }

    // Update previous state for next tick
    for (long i = 0; i < info.mNumVehicles; ++i)
    {
        const auto& v = info.mVehicle[i];
        auto& vs = m_vehicles[v.mID];
        vs.prevPlace        = v.mPlace;
        vs.prevPitState     = v.mPitState;
        vs.prevNumPenalties = v.mNumPenalties;

        // Track tire compounds for pit detection
        if (v.mPitState == 0)
        {
            // Only update "current compound" when NOT in pits
            // so we capture the compound BEFORE pit entry
        }

        vs.lastPos = {v.mPos.x, v.mPos.y, v.mPos.z};
    }
}

// ── ProcessTelemetry (≈50 Hz) ─────────────────────────────────────

void EventDetector::ProcessTelemetry(const TelemInfoV01& info)
{
    DetectCollisions(info);
    DetectOffTrack(info);
}

// ── Collision detection ───────────────────────────────────────────

void EventDetector::DetectCollisions(const TelemInfoV01& info)
{
    if (info.mLastImpactMagnitude < COLLISION_MAGNITUDE_THRESHOLD)
        return;

    auto& vs = GetOrCreateVehicle(info.mID, nullptr);

    // Dedup: same impact timestamp already processed
    if (vs.lastImpactET == info.mLastImpactET)
        return;
    vs.lastImpactET = info.mLastImpactET;

    // Dedup: too close to last collision event for this vehicle
    if (vs.lastCollisionEventET > 0.0 &&
        (info.mElapsedTime - vs.lastCollisionEventET) < COLLISION_DEDUP_SECONDS)
        return;

    vs.lastCollisionEventET = info.mElapsedTime;

    Vec3 impactPos = {info.mLastImpactPos.x, info.mLastImpactPos.y, info.mLastImpactPos.z};
    Vec3 vehiclePos = {info.mPos.x, info.mPos.y, info.mPos.z};

    // Check if any other vehicle is close enough to be "the other party"
    std::string otherDriver;
    for (const auto& sv : m_lastScoring.vehicles)
    {
        if (sv.id == info.mID)
            continue;

        double dist = Distance(vehiclePos, sv.pos);
        if (dist < COLLISION_VEHICLE_DISTANCE)
        {
            otherDriver = sv.name;
            break;
        }
    }

    // Find this vehicle's current lap and lapDist from scoring
    int curLap = info.mLapNumber;
    double curLapDist = 0.0;
    for (const auto& sv : m_lastScoring.vehicles)
    {
        if (sv.id == info.mID)
        {
            curLapDist = sv.lapDist;
            break;
        }
    }

    RaceEvent ev;
    ev.timestampET  = info.mElapsedTime;
    ev.timestampHMS = FormatHMS(info.mElapsedTime);
    ev.lap          = curLap;
    ev.lapDist      = curLapDist;
    ev.position     = impactPos;
    ev.impactMagnitude = info.mLastImpactMagnitude;
    ev.driverPositions = TakeSnapshot();

    if (!otherDriver.empty())
    {
        ev.type = "collision_vehicle";
        ev.driversInvolved = {vs.name, otherDriver};
    }
    else
    {
        ev.type = "collision_wall";
        ev.driversInvolved = {vs.name};
    }

    AddEvent(std::move(ev));
}

// ── Off-track detection ───────────────────────────────────────────

void EventDetector::DetectOffTrack(const TelemInfoV01& info)
{
    auto& vs = GetOrCreateVehicle(info.mID, nullptr);

    // Count wheels on non-road surface (grass=2, dirt=3, gravel=4)
    int offWheels = 0;
    std::string surfName;
    for (int w = 0; w < 4; ++w)
    {
        unsigned char st = info.mWheel[w].mSurfaceType;
        if (st >= 2 && st <= 4)
        {
            ++offWheels;
            if (surfName.empty())
            {
                switch (st)
                {
                    case 2: surfName = "grass";  break;
                    case 3: surfName = "dirt";   break;
                    case 4: surfName = "gravel"; break;
                }
            }
        }
    }

    bool currentlyOff = (offWheels >= OFF_TRACK_MIN_WHEELS);

    if (currentlyOff && !vs.offTrack)
    {
        // Transition: on-track → off-track (only if dedup window passed)
        if (vs.lastOffTrackEventET > 0.0 &&
            (info.mElapsedTime - vs.lastOffTrackEventET) < OFF_TRACK_DEDUP_SECONDS)
        {
            vs.offTrack = true;
            return;
        }

        vs.offTrack = true;
        vs.lastOffTrackEventET = info.mElapsedTime;

        Vec3 pos = {info.mPos.x, info.mPos.y, info.mPos.z};

        // Find lapDist from scoring
        double curLapDist = 0.0;
        for (const auto& sv : m_lastScoring.vehicles)
        {
            if (sv.id == info.mID)
            {
                curLapDist = sv.lapDist;
                break;
            }
        }

        RaceEvent ev;
        ev.type         = "off_track";
        ev.timestampET  = info.mElapsedTime;
        ev.timestampHMS = FormatHMS(info.mElapsedTime);
        ev.lap          = info.mLapNumber;
        ev.lapDist      = curLapDist;
        ev.driversInvolved = {vs.name};
        ev.position     = pos;
        ev.surfaceType  = surfName;
        ev.driverPositions = TakeSnapshot();

        AddEvent(std::move(ev));
    }
    else if (!currentlyOff && vs.offTrack)
    {
        // Back on track
        vs.offTrack = false;
    }
}

// ── Overtake detection ────────────────────────────────────────────

void EventDetector::DetectOvertakes(const ScoringInfoV01& info)
{
    // Purge old dedup entries
    double now = info.mCurrentET;
    m_recentOvertakes.erase(
        std::remove_if(m_recentOvertakes.begin(), m_recentOvertakes.end(),
            [now](const OvertakePair& op) { return (now - op.et) > OVERTAKE_DEDUP_SECONDS; }),
        m_recentOvertakes.end());

    for (long i = 0; i < info.mNumVehicles; ++i)
    {
        const auto& v = info.mVehicle[i];
        auto it = m_vehicles.find(v.mID);
        if (it == m_vehicles.end()) continue;

        int prevPlace = it->second.prevPlace;
        int currPlace = v.mPlace;

        // Skip if no previous data or no change
        if (prevPlace == 0 || prevPlace == currPlace)
            continue;

        // Position improved (lower number = better)
        if (currPlace < prevPlace)
        {
            // Find who was overtaken (the driver who was at currPlace and is now worse)
            for (long j = 0; j < info.mNumVehicles; ++j)
            {
                if (j == i) continue;
                const auto& other = info.mVehicle[j];
                auto oit = m_vehicles.find(other.mID);
                if (oit == m_vehicles.end()) continue;

                int otherPrev = oit->second.prevPlace;
                int otherCurr = other.mPlace;

                // This is the overtaken driver: they were at the position the overtaker now has
                if (otherPrev == currPlace && otherCurr > otherPrev)
                {
                    std::string a = v.mDriverName;
                    std::string b = other.mDriverName;

                    // Dedup check
                    bool isDup = false;
                    for (const auto& op : m_recentOvertakes)
                    {
                        if ((op.a == a && op.b == b) || (op.a == b && op.b == a))
                        {
                            isDup = true;
                            break;
                        }
                    }
                    if (isDup) break;

                    m_recentOvertakes.push_back({a, b, now});

                    RaceEvent ev;
                    ev.type         = "overtake";
                    ev.timestampET  = info.mCurrentET;
                    ev.timestampHMS = FormatHMS(info.mCurrentET);
                    ev.lap          = v.mTotalLaps;
                    ev.lapDist      = v.mLapDist;
                    ev.driversInvolved = {a, b};
                    ev.position     = {v.mPos.x, v.mPos.y, v.mPos.z};
                    ev.newPositions[a] = currPlace;
                    ev.newPositions[b] = otherCurr;
                    ev.driverPositions = TakeSnapshot();

                    AddEvent(std::move(ev));
                    break;
                }
            }
        }
    }
}

// ── Penalty detection ─────────────────────────────────────────────

void EventDetector::DetectPenalties(const ScoringInfoV01& info)
{
    for (long i = 0; i < info.mNumVehicles; ++i)
    {
        const auto& v = info.mVehicle[i];
        auto it = m_vehicles.find(v.mID);
        if (it == m_vehicles.end()) continue;

        if (v.mNumPenalties > it->second.prevNumPenalties)
        {
            RaceEvent ev;
            ev.type         = "penalty";
            ev.timestampET  = info.mCurrentET;
            ev.timestampHMS = FormatHMS(info.mCurrentET);
            ev.lap          = v.mTotalLaps;
            ev.lapDist      = v.mLapDist;
            ev.driversInvolved = {v.mDriverName};
            ev.position     = {v.mPos.x, v.mPos.y, v.mPos.z};
            ev.penaltyCount = v.mNumPenalties;
            ev.driverPositions = TakeSnapshot();

            AddEvent(std::move(ev));
        }
    }
}

// ── Pit stop detection ────────────────────────────────────────────

void EventDetector::DetectPitStops(const ScoringInfoV01& info)
{
    for (long i = 0; i < info.mNumVehicles; ++i)
    {
        const auto& v = info.mVehicle[i];
        auto it = m_vehicles.find(v.mID);
        if (it == m_vehicles.end()) continue;

        auto& vs = it->second;

        // Entering pit box (transition to state 3 = stopped)
        if (v.mPitState == 3 && vs.prevPitState != 3)
        {
            vs.pitEntryET = info.mCurrentET;
            // Capture tire compounds BEFORE pit work (from telemetry state)
            // Note: we use the "prev" compounds stored from on-track driving
        }

        // Exiting pit box (transition from state 3 to 4)
        if (v.mPitState == 4 && vs.prevPitState == 3)
        {
            RaceEvent ev;
            ev.type         = "pit_entry";
            ev.timestampET  = vs.pitEntryET;
            ev.timestampHMS = FormatHMS(vs.pitEntryET);
            ev.lap          = v.mTotalLaps;
            ev.lapDist      = v.mLapDist;
            ev.driversInvolved = {v.mDriverName};
            ev.position     = {v.mPos.x, v.mPos.y, v.mPos.z};
            ev.driverPositions = TakeSnapshot();

            // Determine reason
            bool penaltyServed = (v.mNumPenalties < vs.prevNumPenalties);
            // Tire compounds — read current from telemetry state tracked in UpdateTelemetry
            // Since we don't have direct access to TelemInfoV01 here, we stored them via ProcessTelemetry
            std::string curFront = vs.prevFrontTire;
            std::string curRear  = vs.prevRearTire;

            // After pit stop we'll detect new compounds on next telemetry update
            // For now, record what we know
            if (penaltyServed)
            {
                ev.pitReason = "penalty_served";
                ev.penaltyServed = true;
            }
            else
            {
                // We'll mark as tire_change by default if compounds were tracked
                // The actual compound comparison happens after the pit via telemetry
                ev.pitReason = "service";
            }

            ev.tiresRemovedFront  = curFront;
            ev.tiresRemovedRear   = curRear;

            AddEvent(std::move(ev));
        }
    }
}

// ── Fastest lap detection ─────────────────────────────────────────

void EventDetector::DetectFastestLap(const ScoringInfoV01& info)
{
    for (long i = 0; i < info.mNumVehicles; ++i)
    {
        const auto& v = info.mVehicle[i];
        if (v.mBestLapTime <= 0.0) continue;

        auto it = m_vehicles.find(v.mID);
        if (it == m_vehicles.end()) continue;

        auto& vs = it->second;

        // Check if this driver just set a new personal best
        bool newPersonalBest = (vs.prevBestLapTime < 0.0 || v.mBestLapTime < vs.prevBestLapTime);
        vs.prevBestLapTime = v.mBestLapTime;

        if (!newPersonalBest) continue;

        // Check if it's the overall fastest
        if (m_globalBestLapTime < 0.0 || v.mBestLapTime < m_globalBestLapTime)
        {
            m_globalBestLapTime = v.mBestLapTime;

            RaceEvent ev;
            ev.type         = "fastest_lap";
            ev.timestampET  = info.mCurrentET;
            ev.timestampHMS = FormatHMS(info.mCurrentET);
            ev.lap          = v.mTotalLaps;
            ev.lapDist      = v.mLapDist;
            ev.driversInvolved = {v.mDriverName};
            ev.position     = {v.mPos.x, v.mPos.y, v.mPos.z};
            ev.lapTime      = v.mBestLapTime;
            ev.lapTimeHMS   = FormatLapTimeHMS(v.mBestLapTime);
            ev.driverPositions = TakeSnapshot();

            AddEvent(std::move(ev));
        }
    }
}

// ── Proximity detection (<0.5s gap) ──────────────────────────────

void EventDetector::DetectProximity(const ScoringInfoV01& info)
{
    for (long i = 0; i < info.mNumVehicles; ++i)
    {
        const auto& v = info.mVehicle[i];
        auto it = m_vehicles.find(v.mID);
        if (it == m_vehicles.end()) continue;

        auto& vs = it->second;

        // mTimeBehindNext: time behind the vehicle in the next higher place
        bool withinThreshold = (v.mTimeBehindNext > 0.0 &&
                                v.mTimeBehindNext < PROXIMITY_TRIGGER_GAP);

        if (withinThreshold && !vs.inProximity)
        {
            vs.inProximity = true;

            // Find who is ahead (mPlace - 1)
            std::string aheadDriver;
            for (long j = 0; j < info.mNumVehicles; ++j)
            {
                if (info.mVehicle[j].mPlace == v.mPlace - 1)
                {
                    aheadDriver = info.mVehicle[j].mDriverName;
                    break;
                }
            }

            if (!aheadDriver.empty())
            {
                RaceEvent ev;
                ev.type         = "proximity";
                ev.timestampET  = info.mCurrentET;
                ev.timestampHMS = FormatHMS(info.mCurrentET);
                ev.lap          = v.mTotalLaps;
                ev.lapDist      = v.mLapDist;
                ev.driversInvolved = {std::string(v.mDriverName), aheadDriver};
                ev.position     = {v.mPos.x, v.mPos.y, v.mPos.z};
                ev.gapSeconds   = v.mTimeBehindNext;
                ev.driverPositions = TakeSnapshot();

                AddEvent(std::move(ev));
            }
        }
        else if (!withinThreshold && v.mTimeBehindNext > PROXIMITY_RESET_GAP)
        {
            // Hysteresis reset
            vs.inProximity = false;
        }
    }
}
