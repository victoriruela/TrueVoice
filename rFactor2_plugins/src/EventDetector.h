//───────────────────────────────────────────────────────────────────────
// EventDetector.h — Detects race events from rF2 telemetry & scoring.
//───────────────────────────────────────────────────────────────────────
#ifndef EVENT_DETECTOR_H
#define EVENT_DETECTOR_H

#include "InternalsPlugin.hpp"
#include <string>
#include <vector>
#include <unordered_map>

// ── Shared data types ─────────────────────────────────────────────

struct Vec3 { double x, y, z; };

struct DriverSnapshot
{
    std::string name;
    int         place;
    Vec3        pos;
    double      lapDist;
    int         lap;
};

struct RaceEvent
{
    std::string              type;              // e.g. "collision_vehicle"
    double                   timestampET;
    std::string              timestampHMS;
    int                      lap;
    double                   lapDist;
    std::vector<std::string> driversInvolved;
    Vec3                     position;
    std::vector<DriverSnapshot> driverPositions; // snapshot of everyone

    // Type-specific fields (only one set per event)
    double impactMagnitude   = 0.0;
    double gapSeconds        = 0.0;
    double lapTime           = 0.0;
    std::string lapTimeHMS;
    std::string surfaceType;
    int    penaltyCount      = 0;
    std::string pitReason;
    std::string tiresRemovedFront;
    std::string tiresRemovedRear;
    std::string tiresInstalledFront;
    std::string tiresInstalledRear;
    bool   penaltyServed     = false;
    std::unordered_map<std::string, int> newPositions; // for overtakes
};

struct DriverInfo
{
    long        id;
    std::string name;
    std::string vehicle;
    int         gridPos;
};

struct SessionData
{
    std::string           pluginVersion;
    std::string           trackName;
    double                trackLength   = 0.0;
    std::string           sessionType;
    double                raceStartET   = 0.0;
    int                   numLaps       = 0;
    std::vector<DriverInfo> drivers;
    std::vector<RaceEvent>  events;
};

// ── Per-vehicle tracked state ─────────────────────────────────────

struct VehicleState
{
    long        id           = -1;
    std::string name;
    int         prevPlace    = 0;
    int         prevPitState = 0;
    short       prevNumPenalties = 0;
    double      prevBestLapTime  = -1.0;
    std::string prevFrontTire;
    std::string prevRearTire;
    bool        offTrack     = false;
    bool        inProximity  = false;
    double      lastImpactET = -1.0;
    double      lastCollisionEventET = -1.0;  // dedup window
    double      lastOffTrackEventET  = -1.0;
    Vec3        lastPos      = {0, 0, 0};
    double      pitEntryET   = 0.0;
};

// ── Detector class ────────────────────────────────────────────────

class EventDetector
{
public:
    void Reset();
    void ProcessScoring(const ScoringInfoV01& info);
    void ProcessTelemetry(const TelemInfoV01& info);
    const SessionData& GetSessionData() const { return m_session; }

private:
    // Helpers
    std::string FormatHMS(double elapsedTime) const;
    std::string FormatLapTimeHMS(double lapTime) const;
    std::vector<DriverSnapshot> TakeSnapshot() const;
    VehicleState& GetOrCreateVehicle(long id, const char* name);
    int EstimateLap(double et) const;
    double Distance(const Vec3& a, const Vec3& b) const;

    void AddEvent(RaceEvent&& ev);

    // Detection routines (called from ProcessScoring)
    void DetectOvertakes(const ScoringInfoV01& info);
    void DetectPenalties(const ScoringInfoV01& info);
    void DetectPitStops(const ScoringInfoV01& info);
    void DetectFastestLap(const ScoringInfoV01& info);
    void DetectProximity(const ScoringInfoV01& info);

    // Detection routines (called from ProcessTelemetry)
    void DetectCollisions(const TelemInfoV01& info);
    void DetectOffTrack(const TelemInfoV01& info);

    // State
    SessionData m_session;
    std::unordered_map<long, VehicleState> m_vehicles;
    double m_globalBestLapTime = -1.0;
    double m_raceStartET       = 0.0;
    bool   m_headerCaptured    = false;
    bool   m_racePhaseDetected = false;

    // Scoring snapshot (updated each scoring tick, used by telemetry)
    struct ScoringSnapshot
    {
        struct Entry
        {
            long id;
            std::string name;
            Vec3 pos;
            double lapDist;
            int lap;
            int place;
        };
        std::vector<Entry> vehicles;
        double currentET = 0.0;
    };
    ScoringSnapshot m_lastScoring;

    // Overtake dedup
    struct OvertakePair { std::string a, b; double et; };
    std::vector<OvertakePair> m_recentOvertakes;

    static constexpr double COLLISION_MAGNITUDE_THRESHOLD = 200.0;
    static constexpr double COLLISION_DEDUP_SECONDS       = 5.0;
    static constexpr double COLLISION_VEHICLE_DISTANCE    = 25.0;
    static constexpr double PROXIMITY_TRIGGER_GAP         = 0.5;
    static constexpr double PROXIMITY_RESET_GAP           = 1.0;
    static constexpr double OVERTAKE_DEDUP_SECONDS        = 10.0;
    static constexpr double OFF_TRACK_DEDUP_SECONDS       = 5.0;
    static constexpr int    OFF_TRACK_MIN_WHEELS          = 2;
};

#endif // EVENT_DETECTOR_H
