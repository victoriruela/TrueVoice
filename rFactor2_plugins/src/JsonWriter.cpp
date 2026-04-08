//───────────────────────────────────────────────────────────────────────
// JsonWriter.cpp — Writes SessionData to a JSON file with no external
//                  dependencies beyond the C++ standard library.
//───────────────────────────────────────────────────────────────────────
#include "JsonWriter.h"
#include <cstdio>
#include <fstream>
#include <sstream>
#include <iomanip>

// ── Helpers ───────────────────────────────────────────────────────

std::string JsonWriter::Escape(const std::string& s)
{
    std::string out;
    out.reserve(s.size() + 8);
    for (char c : s)
    {
        switch (c)
        {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\b': out += "\\b";  break;
            case '\f': out += "\\f";  break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:
                if (static_cast<unsigned char>(c) < 0x20)
                {
                    char buf[8];
                    std::snprintf(buf, sizeof(buf), "\\u%04x", static_cast<unsigned char>(c));
                    out += buf;
                }
                else
                {
                    out += c;
                }
        }
    }
    return out;
}

std::string JsonWriter::Quoted(const std::string& s)
{
    return "\"" + Escape(s) + "\"";
}

std::string JsonWriter::FormatDouble(double v, int decimals)
{
    std::ostringstream ss;
    ss << std::fixed << std::setprecision(decimals) << v;
    return ss.str();
}

// ── Write ─────────────────────────────────────────────────────────

bool JsonWriter::Write(const std::string& path, const SessionData& data)
{
    std::ofstream f(path, std::ios::out | std::ios::trunc);
    if (!f.is_open())
        return false;

    // Indent helper
    auto indent = [](int level) -> std::string
    {
        return std::string(level * 2, ' ');
    };

    f << "{\n";
    f << indent(1) << "\"plugin_version\": " << Quoted(data.pluginVersion) << ",\n";
    f << indent(1) << "\"track_name\": "     << Quoted(data.trackName) << ",\n";
    f << indent(1) << "\"track_length\": "   << FormatDouble(data.trackLength, 1) << ",\n";
    f << indent(1) << "\"session_type\": "   << Quoted(data.sessionType) << ",\n";
    f << indent(1) << "\"race_start_et\": "  << FormatDouble(data.raceStartET, 2) << ",\n";
    f << indent(1) << "\"num_laps\": "       << data.numLaps << ",\n";

    // ── Drivers array ─────────────────────────────────────────────
    f << indent(1) << "\"drivers\": [\n";
    for (size_t i = 0; i < data.drivers.size(); ++i)
    {
        const auto& d = data.drivers[i];
        f << indent(2) << "{";
        f << "\"id\": " << d.id
          << ", \"name\": " << Quoted(d.name)
          << ", \"vehicle\": " << Quoted(d.vehicle)
          << ", \"grid_pos\": " << d.gridPos;
        f << "}";
        if (i + 1 < data.drivers.size()) f << ",";
        f << "\n";
    }
    f << indent(1) << "],\n";

    // ── Events array ──────────────────────────────────────────────
    f << indent(1) << "\"events\": [\n";
    for (size_t i = 0; i < data.events.size(); ++i)
    {
        const auto& ev = data.events[i];
        f << indent(2) << "{\n";
        f << indent(3) << "\"type\": "          << Quoted(ev.type) << ",\n";
        f << indent(3) << "\"timestamp_et\": "  << FormatDouble(ev.timestampET, 2) << ",\n";
        f << indent(3) << "\"timestamp_hms\": " << Quoted(ev.timestampHMS) << ",\n";
        f << indent(3) << "\"lap\": "           << ev.lap << ",\n";
        f << indent(3) << "\"lap_dist\": "      << FormatDouble(ev.lapDist, 1) << ",\n";

        // drivers_involved
        f << indent(3) << "\"drivers_involved\": [";
        for (size_t d = 0; d < ev.driversInvolved.size(); ++d)
        {
            f << Quoted(ev.driversInvolved[d]);
            if (d + 1 < ev.driversInvolved.size()) f << ", ";
        }
        f << "],\n";

        // position
        f << indent(3) << "\"position\": {"
          << "\"x\": " << FormatDouble(ev.position.x, 1)
          << ", \"y\": " << FormatDouble(ev.position.y, 1)
          << ", \"z\": " << FormatDouble(ev.position.z, 1)
          << "},\n";

        // Type-specific fields
        if (ev.type == "collision_vehicle" || ev.type == "collision_wall")
        {
            f << indent(3) << "\"impact_magnitude\": " << FormatDouble(ev.impactMagnitude, 1) << ",\n";
        }
        if (ev.type == "off_track")
        {
            f << indent(3) << "\"surface_type\": " << Quoted(ev.surfaceType) << ",\n";
        }
        if (ev.type == "proximity")
        {
            f << indent(3) << "\"gap_seconds\": " << FormatDouble(ev.gapSeconds, 3) << ",\n";
        }
        if (ev.type == "overtake")
        {
            f << indent(3) << "\"new_positions\": {";
            bool first = true;
            for (const auto& [name, pos] : ev.newPositions)
            {
                if (!first) f << ", ";
                f << Quoted(name) << ": " << pos;
                first = false;
            }
            f << "},\n";
        }
        if (ev.type == "penalty")
        {
            f << indent(3) << "\"penalty_count\": " << ev.penaltyCount << ",\n";
        }
        if (ev.type == "pit_entry")
        {
            f << indent(3) << "\"pit_reason\": "          << Quoted(ev.pitReason) << ",\n";
            f << indent(3) << "\"tires_removed\": {"
              << "\"front\": " << Quoted(ev.tiresRemovedFront)
              << ", \"rear\": " << Quoted(ev.tiresRemovedRear) << "},\n";
            f << indent(3) << "\"tires_installed\": {"
              << "\"front\": " << Quoted(ev.tiresInstalledFront)
              << ", \"rear\": " << Quoted(ev.tiresInstalledRear) << "},\n";
            f << indent(3) << "\"penalty_served\": " << (ev.penaltyServed ? "true" : "false") << ",\n";
        }
        if (ev.type == "fastest_lap")
        {
            f << indent(3) << "\"lap_time\": "     << FormatDouble(ev.lapTime, 3) << ",\n";
            f << indent(3) << "\"lap_time_hms\": " << Quoted(ev.lapTimeHMS) << ",\n";
        }

        // driver_positions snapshot
        f << indent(3) << "\"driver_positions\": [\n";
        for (size_t dp = 0; dp < ev.driverPositions.size(); ++dp)
        {
            const auto& snap = ev.driverPositions[dp];
            f << indent(4) << "{"
              << "\"name\": " << Quoted(snap.name)
              << ", \"place\": " << snap.place
              << ", \"pos\": {\"x\": " << FormatDouble(snap.pos.x, 1)
              << ", \"y\": " << FormatDouble(snap.pos.y, 1)
              << ", \"z\": " << FormatDouble(snap.pos.z, 1) << "}"
              << ", \"lap_dist\": " << FormatDouble(snap.lapDist, 1)
              << ", \"lap\": " << snap.lap
              << "}";
            if (dp + 1 < ev.driverPositions.size()) f << ",";
            f << "\n";
        }
        f << indent(3) << "]\n";

        f << indent(2) << "}";
        if (i + 1 < data.events.size()) f << ",";
        f << "\n";
    }
    f << indent(1) << "]\n";

    f << "}\n";

    f.close();
    return true;
}
