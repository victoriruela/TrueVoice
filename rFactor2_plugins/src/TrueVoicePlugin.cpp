//───────────────────────────────────────────────────────────────────────
// TrueVoicePlugin.cpp — Entry point & callbacks for rFactor 2.
//───────────────────────────────────────────────────────────────────────
#include "TrueVoicePlugin.h"
#include <cstring>
#include <exception>
#include <new>
#include <filesystem>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <fstream>
#include <sstream>
#include <string>

namespace fs = std::filesystem;

namespace {

std::string SanitizeFilePart(std::string value)
{
    for (char& ch : value)
    {
        const bool isInvalid =
            ch == '<' || ch == '>' || ch == ':' || ch == '"' ||
            ch == '/' || ch == '\\' || ch == '|' || ch == '?' || ch == '*';
        if (isInvalid || ch == ' ')
            ch = '_';
    }

    // Collapse repeated underscores and trim leading/trailing underscores.
    std::string out;
    out.reserve(value.size());
    bool prevUnderscore = false;
    for (char ch : value)
    {
        if (ch == '_')
        {
            if (prevUnderscore)
                continue;
            prevUnderscore = true;
        }
        else
        {
            prevUnderscore = false;
        }
        out.push_back(ch);
    }
    while (!out.empty() && out.front() == '_')
        out.erase(out.begin());
    while (!out.empty() && out.back() == '_')
        out.pop_back();

    return out.empty() ? "unknown_track" : out;
}

std::string BuildTimestampNow()
{
    const auto now = std::chrono::system_clock::now();
    const std::time_t nowTime = std::chrono::system_clock::to_time_t(now);

    std::tm localTm{};
#if defined(_WIN32)
    localtime_s(&localTm, &nowTime);
#else
    localTm = *std::localtime(&nowTime);
#endif

    std::ostringstream oss;
    oss << std::put_time(&localTm, "%Y%m%d_%H%M%S");
    return oss.str();
}

void AppendDiag(const std::string& userDataPath, const std::string& line)
{
    std::string logDir;
    if (!userDataPath.empty())
    {
        logDir = userDataPath;
        if (logDir.back() != '\\' && logDir.back() != '/')
            logDir += '\\';
        logDir += "Log";
    }
    else
    {
        logDir = ".";
    }

    fs::create_directories(logDir);
    const std::string path = logDir + "\\TrueVoice_plugin_boot.log";

    std::ofstream out(path, std::ios::out | std::ios::app);
    if (!out.is_open())
        return;
    out << BuildTimestampNow() << " " << line << "\n";
}

void AppendExportDiag(const std::string& line)
{
    char tempPath[MAX_PATH] = {};
    DWORD len = GetTempPathA(MAX_PATH, tempPath);

    std::string path;
    if (len > 0 && len < MAX_PATH)
    {
        path = tempPath;
        if (!path.empty() && path.back() != '\\' && path.back() != '/')
            path += '\\';
        path += "TrueVoice_plugin_exports.log";
    }
    else
    {
        path = "TrueVoice_plugin_exports.log";
    }

    std::ofstream out(path, std::ios::out | std::ios::app);
    if (!out.is_open())
        return;
    out << BuildTimestampNow() << " " << line << "\n";
}

bool IsEnabledCaption(const char* caption)
{
    if (!caption)
        return false;

    // rF2 may pass non-terminated caption buffers while probing plugin vars.
    const size_t len = strnlen_s(caption, 128);
    if (len >= 128)
        return false;

    return std::strcmp(caption, " Enabled") == 0;
}

void LogExport(const char* text)
{
    std::string msg = "TrueVoice: ";
    msg += text;
    msg += "\n";
    OutputDebugStringA(msg.c_str());
}

} // namespace

namespace {
class TrueVoicePluginInfo : public InternalsPluginInfo
{
public:
    const char* GetName() const override {
        LogExport("TrueVoicePluginInfo::GetName");
        return "TrueVoice Event Capture";
    }
    const char* GetFullName() const override {
        LogExport("TrueVoicePluginInfo::GetFullName");
        return "TrueVoice Event Capture";
    }
    const char* GetDesc() const override {
        LogExport("TrueVoicePluginInfo::GetDesc");
        return "TrueVoice Event Capture";
    }
    const unsigned GetType() const override {
        LogExport("TrueVoicePluginInfo::GetType");
        return 3; // PT_INTERNALS
    }
    const char* GetSubType() const override {
        LogExport("TrueVoicePluginInfo::GetSubType");
        return "Internals";
    }
    const unsigned GetVersion() const override {
        LogExport("TrueVoicePluginInfo::GetVersion");
        return 7;
    }
    void* Create() const override {
        LogExport("TrueVoicePluginInfo::Create start");
        void* plugin = new TrueVoicePlugin();
        LogExport("TrueVoicePluginInfo::Create ok");
        return plugin;
    }
};
}

// ── DLL Exports (required by rF2) ─────────────────────────────────

extern "C" __declspec(dllexport) const char* __cdecl GetPluginName()
{
    LogExport("GetPluginName");
    return "TrueVoice Event Capture";
}

extern "C" __declspec(dllexport) unsigned __cdecl GetPluginType()
{
    LogExport("GetPluginType");
    return 3; // PT_INTERNALS (confirmed from rFactor2SharedMemoryMapPlugin64.dll)
}

extern "C" __declspec(dllexport) int __cdecl GetPluginVersion()
{
    LogExport("GetPluginVersion");
    return 7; // InternalsPluginV07 API version
}

extern "C" __declspec(dllexport) PluginObjectInfo* __cdecl CreatePluginObject()
{
    LogExport("CreatePluginObject start");
    PluginObjectInfo* obj = new TrueVoicePluginInfo();
    LogExport("CreatePluginObject ok");
    return obj;
}

extern "C" __declspec(dllexport) void __cdecl DestroyPluginObject(PluginObjectInfo* obj)
{
    LogExport("DestroyPluginObject");
    delete obj;
}

// ── Constructor / Destructor ──────────────────────────────────────

TrueVoicePlugin::TrueVoicePlugin()
{
    LogExport("TrueVoicePlugin ctor");
}

TrueVoicePlugin::~TrueVoicePlugin()
{
    LogExport("TrueVoicePlugin dtor");
}

bool TrueVoicePlugin::EnsureCoreInitialized()
{
    if (m_detector && m_writer)
        return true;

    try
    {
        if (!m_detector)
            m_detector = std::make_unique<EventDetector>();
        if (!m_writer)
            m_writer = std::make_unique<JsonWriter>();
        return true;
    }
    catch (const std::exception& ex)
    {
        AppendDiag(m_userDataPath, std::string("EnsureCoreInitialized std::exception: ") + ex.what());
        return false;
    }
    catch (...)
    {
        AppendDiag(m_userDataPath, "EnsureCoreInitialized unknown exception");
        return false;
    }
}

// ── Game Flow ─────────────────────────────────────────────────────

void TrueVoicePlugin::Startup(long version)
{
    LogExport("Startup called");
    // version = rF2 version * 1000
    (void)version;
    if (!EnsureCoreInitialized())
    {
        AppendDiag(m_userDataPath, "Startup core init failed");
        LogExport("Startup failed: EnsureCoreInitialized");
        return;
    }
    AppendDiag(m_userDataPath, "Startup called");
}

void TrueVoicePlugin::Shutdown()
{
    LogExport("Shutdown called");
    AppendDiag(m_userDataPath, "Shutdown called");
    if (m_sessionActive)
        EndSession();
}

void TrueVoicePlugin::SetEnvironment(const EnvironmentInfoV01& info)
{
    LogExport("SetEnvironment called");
    // mPath[0] = UserData directory
    if (info.mPath[0])
        m_userDataPath = info.mPath[0];

    AppendDiag(m_userDataPath, "SetEnvironment called");
}

void TrueVoicePlugin::StartSession()
{
    LogExport("StartSession called");
    if (!EnsureCoreInitialized())
    {
        AppendDiag(m_userDataPath, "StartSession core init failed");
        LogExport("StartSession failed: EnsureCoreInitialized");
        return;
    }

    m_detector->Reset();
    m_sessionActive = true;
    AppendDiag(m_userDataPath, "StartSession called");
}

void TrueVoicePlugin::EndSession()
{
    LogExport("EndSession called");
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

    if (!m_detector || !m_writer)
    {
        AppendDiag(m_userDataPath, "EndSession skipped: core not initialized");
        return;
    }

    const auto& session = m_detector->GetSessionData();
    const std::string ts = BuildTimestampNow();
    const std::string trackPart = SanitizeFilePart(session.trackName);
    const std::string filename = ts + "_" + trackPart + "_events.json";

    m_outputPath = logDir + "\\" + filename;

    // Write the event log
    m_writer->Write(m_outputPath, session);
    AppendDiag(m_userDataPath, std::string("EndSession wrote: ") + filename);
}

void TrueVoicePlugin::EnterRealtime()
{
    LogExport("EnterRealtime");
    m_inRealtime = true;
}

void TrueVoicePlugin::ExitRealtime()
{
    LogExport("ExitRealtime");
    m_inRealtime = false;
}

// ── Scoring callback (≈5 Hz) ─────────────────────────────────────

void TrueVoicePlugin::UpdateScoring(const ScoringInfoV01& info)
{    LogExport("UpdateScoring");    if (!m_sessionActive || !m_enabled)
        return;

    if (!m_detector)
        return;

    m_detector->ProcessScoring(info);
}

// ── Telemetry callback (≈50 Hz) ──────────────────────────────────

void TrueVoicePlugin::UpdateTelemetry(const TelemInfoV01& info)
{
    LogExport("UpdateTelemetry");
    if (!m_sessionActive || !m_inRealtime || !m_enabled)
        return;

    if (!m_detector)
        return;

    m_detector->ProcessTelemetry(info);
}

bool TrueVoicePlugin::GetCustomVariable(long i, CustomVariableV01& var)
{
    LogExport("GetCustomVariable");
    if (i != 0)
        return false;

    std::strncpy(var.mCaption, " Enabled", sizeof(var.mCaption) - 1);
    var.mCaption[sizeof(var.mCaption) - 1] = '\0';
    var.mNumSettings = 2;
    var.mCurrentSetting = m_enabled ? 1 : 0;
    return true;
}

void TrueVoicePlugin::AccessCustomVariable(CustomVariableV01& var)
{
    LogExport("AccessCustomVariable");
    if (IsEnabledCaption(var.mCaption))
    {
        m_enabled = (var.mCurrentSetting != 0);
        AppendDiag(m_userDataPath, std::string("Custom var Enabled=") + (m_enabled ? "1" : "0"));
    }
}

void TrueVoicePlugin::GetCustomVariableSetting(CustomVariableV01& var, long i, CustomSettingV01& setting)
{
    LogExport("GetCustomVariableSetting");
    setting.mName[0] = '\0';

    if (!IsEnabledCaption(var.mCaption))
        return;

    if (i == 0)
    {
        std::strncpy(setting.mName, "Off", sizeof(setting.mName) - 1);
        setting.mName[sizeof(setting.mName) - 1] = '\0';
    }
    else if (i == 1)
    {
        std::strncpy(setting.mName, "On", sizeof(setting.mName) - 1);
        setting.mName[sizeof(setting.mName) - 1] = '\0';
    }
}
bool TrueVoicePlugin::WantsScoringUpdates()
{
    LogExport("WantsScoringUpdates");
    return true;
}

long TrueVoicePlugin::WantsTelemetryUpdates()
{
    LogExport("WantsTelemetryUpdates");
    return 2;
}
