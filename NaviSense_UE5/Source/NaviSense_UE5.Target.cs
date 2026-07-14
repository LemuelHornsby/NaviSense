// Copyright NaviSyn Marine Solutions. Game target for NaviSense_UE5.
using UnrealBuildTool;
using System.Collections.Generic;

public class NaviSense_UE5Target : TargetRules
{
    public NaviSense_UE5Target(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("NaviSense");
    }
}
