//───────────────────────────────────────────────────────────────────────
// JsonWriter.h — Minimal JSON writer for TrueVoice event output.
//───────────────────────────────────────────────────────────────────────
#ifndef JSON_WRITER_H
#define JSON_WRITER_H

#include "EventDetector.h"
#include <string>

class JsonWriter
{
public:
    bool Write(const std::string& path, const SessionData& data);

private:
    // Helpers
    static std::string Escape(const std::string& s);
    static std::string Quoted(const std::string& s);
    static std::string FormatDouble(double v, int decimals = 1);
};

#endif // JSON_WRITER_H
