// Copyright NaviSyn Marine Solutions. Editor target for NaviSense_UE5.
using UnrealBuildTool;
using System.Collections.Generic;

public class NaviSense_UE5EditorTarget : TargetRules
{
    public NaviSense_UE5EditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V6;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("NaviSense");
    }
}
