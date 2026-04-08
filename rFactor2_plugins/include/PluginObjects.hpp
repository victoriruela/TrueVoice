//───────────────────────────────────────────────────────────────────────
// PluginObjects.hpp — Base class for rFactor 2 plugin objects.
// From https://www.studio-397.com/modding-resources/
// Sourced via TheIronWolfModding/rF2SharedMemoryMapPlugin (MIT)
//───────────────────────────────────────────────────────────────────────
#ifndef _PLUGIN_OBJECTS_HPP_
#define _PLUGIN_OBJECTS_HPP_

class PluginObject
{
public:
    PluginObject() {}
    virtual ~PluginObject() {}

    virtual const char* GetType()    const = 0;
    virtual const int   GetVersion() const = 0;

    virtual void Destroy() { delete this; }
};

class PluginObjectInfo
{
public:
    PluginObjectInfo() {}
    virtual ~PluginObjectInfo() {}

    virtual const char*    GetName()     const = 0;
    virtual const char*    GetFullName() const = 0;
    virtual const char*    GetDesc()     const = 0;
    virtual const unsigned GetType()     const = 0;
    virtual const char*    GetSubType()  const = 0;
    virtual const unsigned GetVersion()  const = 0;
    virtual void*          Create()      const = 0;
};

class InternalsPluginInfo : public PluginObjectInfo
{
public:
    InternalsPluginInfo() {}
    virtual ~InternalsPluginInfo() {}

    const char*    GetName()     const override { return "InternalsPlugin"; }
    const char*    GetFullName() const override { return "InternalsPlugin"; }
    const char*    GetDesc()     const override { return "InternalsPlugin"; }
    const unsigned GetType()     const override { return 7; }
    const char*    GetSubType()  const override { return "Internals"; }
    const unsigned GetVersion()  const override { return 7; }
    void*          Create()      const override { return nullptr; }
};

#endif // _PLUGIN_OBJECTS_HPP_
