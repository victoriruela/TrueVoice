//───────────────────────────────────────────────────────────────────────
// TrueVoicePlugin.cpp — Entry point & callbacks for rFactor 2.
//───────────────────────────────────────────────────────────────────────
#include "TrueVoicePlugin.h"
#include <cstring>
#include <filesystem>

namespace fs = std::filesystem;

// ── DLL Exports (required by rF2) ─────────────────────────────────

static TrueVoicePlugin* g_plugin = nullptr;

extern "C" __declspec(dllexport) const char* GetPluginName()    { return "TrueVoice Event Capture"; }
extern "C" __declspec(dllexport) unsigned GetPluginType()       { return 7; } // InternalsPluginV07
extern "C" __declspec(dllexport) int GetPluginVersion()         { return 3; } // plugin iteration
extern "C" __declspec(dllexport) unsigned char GetPluginSubType()       { return 0; }

extern "C" __declspec(dllexport) PluginObject* CreatePluginObject()
{
    if (!g_plugin)
        g_plugin = new TrueVoicePlugin();
    return g_plugin;
}

extern "C" __declspec(dllexport) void DestroyPluginObject(PluginObject* obj)
{
    if (obj == g_plugin)
    {
        delete g_plugin;
        g_plugin = nullptr;
    }
}

// ── Constructor / Destructor ──────────────────────────────────────

TrueVoicePlugin::TrueVoicePlugin()  = default;
TrueVoicePlugin::~TrueVoicePlugin() = default;

// ── Game Flow ─────────────────────────────────────────────────────

void TrueVoicePlugin::Startup(long version)
{
    // version = rF2 version * 1000
}

void TrueVoicePlugin::Shutdown()
{
    if (m_sessionActive)
        EndSession();
}

void TrueVoicePlugin::SetEnvironment(const EnvironmentInfoV01& info)
{
    // mPath[0] = UserData directory
    if (info.mPath[0])
        m_userDataPath = info.mPath[0];
}

void TrueVoicePlugin::StartSession()
{
    m_detector.Reset();
    m_sessionActive = true;
}

void TrueVoicePlugin::EndSession()
{
    if (!m_sessionActive)
        return;

    m_sessionActive = false;

    // Build output path
    std::string logDir;
    if (!m_userDataPath.empty())
    {
        logDir = m_userDataPath;
        // Ensure trailing separator
        if (logDir.back() != '\\' && logDir.back() != '/')
            logDir += '\\';
        logDir += "Log";
    }
    else
    {
        logDir = ".";
    }

    // Create directory if needed
    fs::create_directories(logDir);

    m_outputPath = logDir + "\\TrueVoice_events.json";

    // Write the event log
    m_writer.Write(m_outputPath, m_detector.GetSessionData());
}

void TrueVoicePlugin::EnterRealtime()
{
    m_inRealtime = true;
}

void TrueVoicePlugin::ExitRealtime()
{
    m_inRealtime = false;
}

// ── Scoring callback (≈5 Hz) ─────────────────────────────────────

void TrueVoicePlugin::UpdateScoring(const ScoringInfoV01& info)
{
    if (!m_sessionActive)
        return;

    m_detector.ProcessScoring(info);
}

// ── Telemetry callback (≈50 Hz) ──────────────────────────────────

void TrueVoicePlugin::UpdateTelemetry(const TelemInfoV01& info)
{
    if (!m_sessionActive || !m_inRealtime)
        return;

    m_detector.ProcessTelemetry(info);
}
