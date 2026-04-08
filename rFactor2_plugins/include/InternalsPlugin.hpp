//───────────────────────────────────────────────────────────────────────
// InternalsPlugin.hpp — rFactor 2 Internals Plugin SDK header (V07).
// From https://www.studio-397.com/modding-resources/
// Sourced via TheIronWolfModding/rF2SharedMemoryMapPlugin (MIT)
//
// IMPORTANT: rF2 requires #pragma pack(push, 4) for all shared structs.
//───────────────────────────────────────────────────────────────────────
#ifndef _INTERNALS_PLUGIN_HPP_
#define _INTERNALS_PLUGIN_HPP_

#include "PluginObjects.hpp"
#include <cmath>
#include <windows.h>

#pragma pack(push, 4)

// ── Basic types ────────────────────────────────────────────────────

struct TelemVect3
{
    double x, y, z;
    void Set(const double a, const double b, const double c) { x = a; y = b; z = c; }
    double&       operator[](long i)       { return (&x)[i]; }
    const double& operator[](long i) const { return (&x)[i]; }
};

// ── Wheel telemetry ────────────────────────────────────────────────

struct TelemWheelV01
{
    double mSuspensionDeflection;   // meters
    double mRideHeight;             // meters
    double mSuspForce;              // pushrod load in Newtons
    double mBrakeTemp;              // Celsius
    double mBrakePressure;          // 0.0-1.0 (will be kPa in future)
    double mRotation;               // rad/s
    double mLateralPatchVel;
    double mLongitudinalPatchVel;
    double mLateralGroundVel;
    double mLongitudinalGroundVel;
    double mCamber;                 // radians
    double mLateralForce;           // Newtons
    double mLongitudinalForce;      // Newtons
    double mTireLoad;               // Newtons
    double mGripFract;              // fraction of contact patch sliding
    double mPressure;               // kPa
    double mTemperature[3];         // Kelvin (left/center/right)
    double mWear;                   // 0.0-1.0
    char   mTerrainName[16];
    unsigned char mSurfaceType;     // 0=dry,1=wet,2=grass,3=dirt,4=gravel,5=rumblestrip,6=special
    bool   mFlat;
    bool   mDetached;
    unsigned char mStaticUndeflectedRadius; // cm
    double mVerticalTireDeflection;
    double mWheelYLocation;
    double mToe;
    double mTireCarcassTemperature;
    double mTireInnerLayerTemperature[3];
    unsigned char mExpansion[24];
};

// ── Vehicle telemetry (≈50 Hz) ─────────────────────────────────────

struct TelemInfoV01
{
    long       mID;
    double     mDeltaTime;
    double     mElapsedTime;
    long       mLapNumber;
    double     mLapStartET;
    char       mVehicleName[64];
    char       mTrackName[64];

    // Position & derivatives
    TelemVect3 mPos;
    TelemVect3 mLocalVel;
    TelemVect3 mLocalAccel;

    // Orientation
    TelemVect3 mOri[3];
    TelemVect3 mLocalRot;
    TelemVect3 mLocalRotAccel;

    // Vehicle status
    long       mGear;
    double     mEngineRPM;
    double     mEngineWaterTemp;
    double     mEngineOilTemp;
    double     mClutchRPM;

    // Driver input (unfiltered)
    double     mUnfilteredThrottle;
    double     mUnfilteredBrake;
    double     mUnfilteredSteering;
    double     mUnfilteredClutch;

    // Filtered input
    double     mFilteredThrottle;
    double     mFilteredBrake;
    double     mFilteredSteering;
    double     mFilteredClutch;

    // Misc
    double     mSteeringShaftTorque;
    double     mFront3rdDeflection;
    double     mRear3rdDeflection;

    // Aero
    double     mFrontWingHeight;
    double     mFrontRideHeight;
    double     mRearRideHeight;
    double     mDrag;
    double     mFrontDownforce;
    double     mRearDownforce;

    // State / damage
    double     mFuel;
    double     mEngineMaxRPM;
    unsigned char mScheduledStops;
    bool       mOverheating;
    bool       mDetached;
    bool       mHeadlights;
    unsigned char mDentSeverity[8];
    double     mLastImpactET;
    double     mLastImpactMagnitude;
    TelemVect3 mLastImpactPos;

    // Expanded
    double     mEngineTorque;
    long       mCurrentSector;
    unsigned char mSpeedLimiter;
    unsigned char mMaxGears;
    unsigned char mFrontTireCompoundIndex;
    unsigned char mRearTireCompoundIndex;
    double     mFuelCapacity;
    unsigned char mFrontFlapActivated;
    unsigned char mRearFlapActivated;
    unsigned char mRearFlapLegalStatus;
    unsigned char mIgnitionStarter;

    char       mFrontTireCompoundName[18];
    char       mRearTireCompoundName[18];

    unsigned char mSpeedLimiterAvailable;
    unsigned char mAntiStallActivated;
    unsigned char mUnused[2];
    float      mVisualSteeringWheelRange;
    double     mRearBrakeBias;
    double     mTurboBoostPressure;
    float      mPhysicsToGraphicsOffset[3];
    float      mPhysicalSteeringWheelRange;
    double     mDeltaBest;
    double     mBatteryChargeFraction;

    // Electric boost motor
    double     mElectricBoostMotorTorque;
    double     mElectricBoostMotorRPM;
    double     mElectricBoostMotorTemperature;
    double     mElectricBoostWaterTemperature;
    unsigned char mElectricBoostMotorState;

    unsigned char mExpansion[103];

    TelemWheelV01 mWheel[4]; // FL, FR, RL, RR
};

// ── Vehicle scoring (≈5 Hz) ───────────────────────────────────────

struct VehicleScoringInfoV01
{
    long       mID;
    char       mDriverName[32];
    char       mVehicleName[64];
    short      mTotalLaps;
    signed char mSector;           // 0=sector3, 1=sector1, 2=sector2
    signed char mFinishStatus;     // 0=none, 1=finished, 2=dnf, 3=dq
    double     mLapDist;
    double     mPathLateral;
    double     mTrackEdge;

    double     mBestSector1;
    double     mBestSector2;
    double     mBestLapTime;
    double     mLastSector1;
    double     mLastSector2;
    double     mLastLapTime;
    double     mCurSector1;
    double     mCurSector2;

    short      mNumPitstops;
    short      mNumPenalties;
    bool       mIsPlayer;
    signed char mControl;          // -1=nobody, 0=player, 1=AI, 2=remote, 3=replay
    bool       mInPits;
    unsigned char mPlace;          // 1-based
    char       mVehicleClass[32];

    double     mTimeBehindNext;
    long       mLapsBehindNext;
    double     mTimeBehindLeader;
    long       mLapsBehindLeader;
    double     mLapStartET;

    TelemVect3 mPos;
    TelemVect3 mLocalVel;
    TelemVect3 mLocalAccel;
    TelemVect3 mOri[3];
    TelemVect3 mLocalRot;
    TelemVect3 mLocalRotAccel;

    unsigned char mHeadlights;
    unsigned char mPitState;       // 0=none, 1=request, 2=entering, 3=stopped, 4=exiting
    unsigned char mServerScored;
    unsigned char mIndividualPhase;

    long       mQualification;

    double     mTimeIntoLap;
    double     mEstimatedLapTime;

    char       mPitGroup[24];
    unsigned char mFlag;           // 0=green, 6=blue
    bool       mUnderYellow;
    unsigned char mCountLapFlag;
    bool       mInGarageStall;

    unsigned char mUpgradePack[16];
    float      mPitLapDist;

    float      mBestLapSector1;
    float      mBestLapSector2;

    unsigned char mExpansion[48];
};

// ── Session scoring info (≈5 Hz) ──────────────────────────────────

struct ScoringInfoV01
{
    char       mTrackName[64];
    long       mSession;           // 0=testday,1-4=practice,5-8=qual,9=warmup,10-13=race
    double     mCurrentET;
    double     mEndET;
    long       mMaxLaps;
    double     mLapDist;           // track length
    char*      mResultsStream;

    long       mNumVehicles;

    // Game phase: 0=before, 1=recon, 2=grid, 3=formation, 4=countdown,
    //             5=green, 6=FCY/SC, 7=stopped, 8=over, 9=paused
    unsigned char mGamePhase;

    signed char mYellowFlagState;
    signed char mSectorFlag[3];
    unsigned char mStartLight;
    unsigned char mNumRedLights;
    bool       mInRealtime;
    char       mPlayerName[32];
    char       mPlrFileName[64];

    // Weather
    double     mDarkCloud;
    double     mRaining;
    double     mAmbientTemp;
    double     mTrackTemp;
    TelemVect3 mWind;
    double     mMinPathWetness;
    double     mMaxPathWetness;

    // Multiplayer
    unsigned char  mGameMode;
    bool           mIsPasswordProtected;
    unsigned short mServerPort;
    unsigned long  mServerPublicIP;
    long           mMaxPlayers;
    char           mServerName[32];
    float          mStartET;

    double     mAvgPathWetness;

    unsigned char mExpansion[200];

    VehicleScoringInfoV01* mVehicle;
};

// ── Graphics info ──────────────────────────────────────────────────

struct GraphicsInfoV01
{
    TelemVect3 mCamPos;
    TelemVect3 mCamOri[3];
    HWND       mHWND;
    double     mAmbientRed;
    double     mAmbientGreen;
    double     mAmbientBlue;
};

struct GraphicsInfoV02 : public GraphicsInfoV01
{
    long mID;
    long mCameraType;
    unsigned char mExpansion[128];
};

// ── Commentary ─────────────────────────────────────────────────────

struct CommentaryRequestInfoV01
{
    char   mName[32];
    double mInput1;
    double mInput2;
    double mInput3;
    bool   mSkipChecks;
    CommentaryRequestInfoV01() { mName[0] = 0; mInput1 = 0.0; mInput2 = 0.0; mInput3 = 0.0; mSkipChecks = false; }
};

// ── Physics options ────────────────────────────────────────────────

struct PhysicsOptionsV01
{
    unsigned char mTractionControl;
    unsigned char mAntiLockBrakes;
    unsigned char mStabilityControl;
    unsigned char mAutoShift;
    unsigned char mAutoClutch;
    unsigned char mInvulnerable;
    unsigned char mOppositeLock;
    unsigned char mSteeringHelp;
    unsigned char mBrakingHelp;
    unsigned char mSpinRecovery;
    unsigned char mAutoPit;
    unsigned char mAutoLift;
    unsigned char mAutoBlip;
    unsigned char mFuelMult;
    unsigned char mTireMult;
    unsigned char mMechFail;
    unsigned char mAllowPitcrewPush;
    unsigned char mRepeatShifts;
    unsigned char mHoldClutch;
    unsigned char mAutoReverse;
    unsigned char mAlternateNeutral;
    unsigned char mAIControl;
    unsigned char mUnused1;
    unsigned char mUnused2;
    float mManualShiftOverrideTime;
    float mAutoShiftOverrideTime;
    float mSpeedSensitiveSteering;
    float mSteerRatioSpeed;
};

// ── Environment ────────────────────────────────────────────────────

struct EnvironmentInfoV01
{
    const char* mPath[16];
    unsigned char mExpansion[256];
};

// ── Screen info ────────────────────────────────────────────────────

struct ScreenInfoV01
{
    HWND mAppWindow;
    void* mDevice;
    void* mRenderTarget;
    long mDriver;
    long mWidth;
    long mHeight;
    long mPixelFormat;
    long mRefreshRate;
    long mWindowed;
    long mOptionsWidth;
    long mOptionsHeight;
    long mOptionsLeft;
    long mOptionsUpper;
    unsigned char mOptionsLocation;
    char mOptionsPage[31];
    unsigned char mExpansion[224];
};

// ── Custom control ─────────────────────────────────────────────────

struct CustomControlInfoV01
{
    char mUntranslatedName[64];
    long mRepeat;
    unsigned char mExpansion[64];
};

// ── Weather control ────────────────────────────────────────────────

struct WeatherControlInfoV01
{
    double mET;
    double mRaining[3][3];
    double mCloudiness;
    double mAmbientTempK;
    double mWindMaxSpeed;
    bool   mApplyCloudinessInstantly;
    bool   mUnused1;
    bool   mUnused2;
    bool   mUnused3;
    unsigned char mExpansion[508];
};

// ── Message info ───────────────────────────────────────────────────

struct MessageInfoV01
{
    char mText[128];
    unsigned char mDestination;
    unsigned char mTranslate;
    unsigned char mExpansion[126];
};

// ── Camera control ─────────────────────────────────────────────────

struct CameraControlInfoV01
{
    long mID;
    long mCameraType;
    bool mReplayActive;
    bool mReplayUnused;
    unsigned char mReplayCommand;
    bool  mReplaySetTime;
    float mReplaySeconds;
    unsigned char mExpansion[120];
};

// ── Custom plugin variables (V07) ──────────────────────────────────

struct CustomVariableV01
{
    char mCaption[128];
    long mNumSettings;
    long mCurrentSetting;
    unsigned char mExpansion[256];
};

struct CustomSettingV01
{
    char mName[128];
};

// ── Multi-session (V07) ────────────────────────────────────────────

struct MultiSessionParticipantV01
{
    long mID;
    char mDriverName[32];
    char mVehicleName[64];
    unsigned char mUpgradePack[16];
    float mBestPracticeTime;
    long  mQualParticipantIndex;
    float mQualificationTime[4];
    float mFinalRacePlace[4];
    float mFinalRaceTime[4];
    bool  mServerScored;
    long  mGridPosition;
    unsigned char mExpansion[128];
};

struct MultiSessionRulesV01
{
    long mSession;
    long mSpecialSlotID;
    char mTrackType[32];
    long mNumParticipants;
    MultiSessionParticipantV01* mParticipant;
    long mNumQualSessions;
    long mNumRaceSessions;
    long mMaxLaps;
    long mMaxSeconds;
    char mName[32];
    unsigned char mExpansion[256];
};

// ── Track rules (V07) ─────────────────────────────────────────────

enum TrackRulesCommandV01
{
    TRCMD_ADD_FROM_TRACK = 0,
    TRCMD_ADD_FROM_PIT,
    TRCMD_ADD_FROM_UNDQ,
    TRCMD_REMOVE_TO_PIT,
    TRCMD_REMOVE_TO_DNF,
    TRCMD_REMOVE_TO_DQ,
    TRCMD_REMOVE_TO_UNLOADED,
    TRCMD_MOVE_TO_BACK,
    TRCMD_LONGEST_LINE,
    TRCMD_MAXIMUM
};

enum TrackRulesColumnV01
{
    TRCOL_LEFT_LANE = 0,
    TRCOL_MIDLEFT_LANE,
    TRCOL_MIDDLE_LANE,
    TRCOL_MIDRIGHT_LANE,
    TRCOL_RIGHT_LANE,
    TRCOL_MAX_LANES,
    TRCOL_INVALID = TRCOL_MAX_LANES,
    TRCOL_FREECHOICE,
    TRCOL_PENDING,
    TRCOL_MAXIMUM
};

struct TrackRulesActionV01 { TrackRulesCommandV01 mCommand; long mID; double mET; };

struct TrackRulesParticipantV01
{
    long mID;
    short mFrozenOrder;
    short mPlace;
    float mYellowSeverity;
    double mCurrentRelativeDistance;
    long mRelativeLaps;
    TrackRulesColumnV01 mColumnAssignment;
    long mPositionAssignment;
    unsigned char mPitsOpen;
    bool mUpToSpeed;
    bool mUnused[2];
    double mGoalRelativeDistance;
    char mMessage[96];
    unsigned char mExpansion[192];
};

enum TrackRulesStageV01
{
    TRSTAGE_FORMATION_INIT = 0,
    TRSTAGE_FORMATION_UPDATE,
    TRSTAGE_NORMAL,
    TRSTAGE_CAUTION_INIT,
    TRSTAGE_CAUTION_UPDATE,
    TRSTAGE_MAXIMUM
};

struct TrackRulesV01
{
    double mCurrentET;
    TrackRulesStageV01 mStage;
    TrackRulesColumnV01 mPoleColumn;
    long mNumActions;
    TrackRulesActionV01* mAction;
    long mNumParticipants;
    bool mYellowFlagDetected;
    unsigned char mYellowFlagLapsWasOverridden;
    bool mSafetyCarExists;
    bool mSafetyCarActive;
    long mSafetyCarLaps;
    float mSafetyCarThreshold;
    double mSafetyCarLapDist;
    float mSafetyCarLapDistAtStart;
    float mPitLaneStartDist;
    float mTeleportLapDist;
    unsigned char mInputExpansion[256];
    signed char mYellowFlagState;
    short mYellowFlagLaps;
    long mSafetyCarInstruction;
    float mSafetyCarSpeed;
    float mSafetyCarMinimumSpacing;
    float mSafetyCarMaximumSpacing;
    float mMinimumColumnSpacing;
    float mMaximumColumnSpacing;
    float mMinimumSpeed;
    float mMaximumSpeed;
    char mMessage[96];
    TrackRulesParticipantV01* mParticipant;
    unsigned char mInputOutputExpansion[256];
};

// ── Pit menu (V07) ────────────────────────────────────────────────

struct PitMenuV01
{
    long mCategoryIndex;
    char mCategoryName[32];
    long mChoiceIndex;
    char mChoiceString[32];
    long mNumChoices;
    unsigned char mExpansion[256];
};


// ========================================================================
// Plugin class hierarchy
// ========================================================================

class InternalsPlugin : public PluginObject
{
public:
    InternalsPlugin() {}
    virtual ~InternalsPlugin() {}

    const char* GetType()    const override { return "InternalsPlugin"; }
    const int   GetVersion() const override { return 7; }

    // GAME FLOW
    virtual void Startup(long version) {}
    virtual void Shutdown() {}
    virtual void Load() {}
    virtual void Unload() {}
    virtual void StartSession() {}
    virtual void EndSession() {}
    virtual void EnterRealtime() {}
    virtual void ExitRealtime() {}

    // SCORING
    virtual bool WantsScoringUpdates() { return false; }
    virtual void UpdateScoring(const ScoringInfoV01& info) {}

    // TELEMETRY
    virtual long WantsTelemetryUpdates() { return 0; }
    virtual void UpdateTelemetry(const TelemInfoV01& info) {}

    // GRAPHICS
    virtual bool WantsGraphicsUpdates() { return false; }
    virtual void UpdateGraphics(const GraphicsInfoV01& info) {}

    // COMMENTARY
    virtual bool RequestCommentary(CommentaryRequestInfoV01& info) { return false; }

    // HARDWARE
    virtual bool HasHardwareInputs() { return false; }
    virtual void UpdateHardware(const double fDT) {}
    virtual void EnableHardware() {}
    virtual void DisableHardware() {}
    virtual bool CheckHWControl(const char* const controlName, double& fRetVal) { return false; }
    virtual bool ForceFeedback(double& forceValue) { return false; }

    // ERROR
    virtual void Error(const char* const msg) {}
};

class InternalsPluginV01 : public InternalsPlugin {};

class InternalsPluginV02 : public InternalsPluginV01
{
public:
    virtual void SetPhysicsOptions(PhysicsOptionsV01& options) {}
};

class InternalsPluginV03 : public InternalsPluginV02
{
public:
    virtual unsigned char WantsToViewVehicle(CameraControlInfoV01& camControl) { return 0; }
    virtual void UpdateGraphics(const GraphicsInfoV02& info) {}
    virtual bool WantsToDisplayMessage(MessageInfoV01& msgInfo) { return false; }
};

class InternalsPluginV04 : public InternalsPluginV03
{
public:
    virtual void SetEnvironment(const EnvironmentInfoV01& info) {}
};

class InternalsPluginV05 : public InternalsPluginV04
{
public:
    virtual void InitScreen(const ScreenInfoV01& info) {}
    virtual void UninitScreen(const ScreenInfoV01& info) {}
    virtual void DeactivateScreen(const ScreenInfoV01& info) {}
    virtual void ReactivateScreen(const ScreenInfoV01& info) {}
    virtual void RenderScreenBeforeOverlays(const ScreenInfoV01& info) {}
    virtual void RenderScreenAfterOverlays(const ScreenInfoV01& info) {}
    virtual void PreReset(const ScreenInfoV01& info) {}
    virtual void PostReset(const ScreenInfoV01& info) {}
    virtual bool InitCustomControl(CustomControlInfoV01& info) { return false; }
};

class InternalsPluginV06 : public InternalsPluginV05
{
public:
    virtual bool WantsWeatherAccess() { return false; }
    virtual bool AccessWeather(double trackNodeSize, WeatherControlInfoV01& info) { return false; }
    virtual void ThreadStarted(long type) {}
    virtual void ThreadStopping(long type) {}
};

class InternalsPluginV07 : public InternalsPluginV06
{
public:
    virtual bool GetCustomVariable(long i, CustomVariableV01& var) { return false; }
    virtual void AccessCustomVariable(CustomVariableV01& var) {}
    virtual void GetCustomVariableSetting(CustomVariableV01& var, long i, CustomSettingV01& setting) {}
    virtual bool WantsMultiSessionRulesAccess() { return false; }
    virtual bool AccessMultiSessionRules(MultiSessionRulesV01& info) { return false; }
    virtual bool WantsTrackRulesAccess() { return false; }
    virtual bool AccessTrackRules(TrackRulesV01& info) { return false; }
    virtual bool WantsPitMenuAccess() { return false; }
    virtual bool AccessPitMenu(PitMenuV01& info) { return false; }
};

#pragma pack(pop)

#endif // _INTERNALS_PLUGIN_HPP_
