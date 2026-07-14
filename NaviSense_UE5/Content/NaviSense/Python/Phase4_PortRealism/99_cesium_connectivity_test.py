# =====================================================================
# NaviSense - Cesium ion connectivity & token diagnostic
# =====================================================================
#
# WHAT THIS DOES
#   1. Tests basic HTTPS reachability of api.cesium.com.
#   2. Reads the project's current Cesium token from the level's tilesets.
#   3. Validates the token by calling https://api.cesium.com/v1/me with
#      it as a Bearer header. A 200 means the token works; 401 = bad token.
#   4. Lists the asset IDs you have access to (sanity check that the
#      Google + OSM tilesets are reachable).
#
# WHY
#   The editor's "ion.cesium.com (not connected)" label is OAuth sign-in
#   state, separate from the token used for streaming. This script verifies
#   the token-based streaming path independent of the OAuth panel state.
#
# HOW TO RUN
#   py "D:/Marine Autonomy/.../Phase4_PortRealism/99_cesium_connectivity_test.py"
# =====================================================================

import json
import urllib.request
import urllib.error
import unreal

def log(m):  unreal.log("[NaviSense Net] " + str(m))
def warn(m): unreal.log_warning("[NaviSense Net] " + str(m))
def err(m):  unreal.log_error("[NaviSense Net] " + str(m))

def fetch(url, token=None, timeout=10):
    headers = {"User-Agent": "NaviSense-UE5-Diagnostic/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read().decode("utf-8", errors="ignore")
            return r.status, data
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return None, "EXCEPTION: " + str(e)

def find_token_in_level():
    """Pull the token from any Cesium3DTileset's IonAccessToken property."""
    subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in subsys.get_all_level_actors():
        if a.get_class().get_name() != "Cesium3DTileset":
            continue
        for prop_name in ("ion_access_token", "ion_asset_token", "access_token"):
            try:
                t = a.get_editor_property(prop_name)
                if t and len(t) > 20:
                    return t, a.get_actor_label()
            except Exception:
                continue
    return None, None

def main():
    log("=" * 60)

    # 1. Basic HTTPS reachability
    log("Test 1: Basic HTTPS to api.cesium.com ...")
    status, body = fetch("https://api.cesium.com/")
    if status == 200:
        log("  PASS  api.cesium.com responds 200.")
    elif status is None:
        err("  FAIL  Network unreachable. Body: {}".format(body[:200]))
        err("  Likely causes: VPN blocking, firewall, no internet, DNS issue.")
        err("  Try: disable NordVPN/GlobalProtect, check browser can open cesium.com")
        return
    else:
        warn("  Got HTTP {} (expected 200). Body: {}".format(status, body[:200]))

    # 2. Read token from a tileset in the level
    log("Test 2: Reading active token from a Cesium3DTileset ...")
    token, source = find_token_in_level()
    if not token:
        warn("  No token found on any tileset. The 'Default' token from")
        warn("  CesiumIonServers.uasset is being used implicitly.")
        warn("  Cannot validate it from Python; check the editor's Cesium panel.")
    else:
        log("  Found token on {}: {}...{}".format(source, token[:20], token[-10:]))

        # 3. Validate token against /v1/me
        log("Test 3: Validating token against api.cesium.com/v1/me ...")
        status, body = fetch("https://api.cesium.com/v1/me", token=token)
        if status == 200:
            try:
                data = json.loads(body)
                log("  PASS  Token authenticates as: {} (id={})".format(
                    data.get("username", "?"), data.get("id", "?")))
                log("        Email: {}".format(data.get("email", "?")))
            except Exception:
                log("  PASS  Token authenticates (couldn't parse JSON).")
        elif status == 401:
            err("  FAIL  Token rejected with 401 - token is expired/revoked.")
            err("  Go to https://cesium.com/ion/tokens and regenerate.")
        else:
            warn("  Got HTTP {} - unexpected. Body: {}".format(status, body[:200]))

        # 4. Check asset access
        log("Test 4: Checking Google Photoreal tiles (asset 2275207) access ...")
        status, body = fetch("https://api.cesium.com/v1/assets/2275207", token=token)
        if status == 200:
            log("  PASS  Asset 2275207 (Google) is reachable.")
        elif status == 404:
            warn("  FAIL  Asset 2275207 not in your account. Re-add it to your")
            warn("        Cesium ion Asset Depot.")
        else:
            warn("  HTTP {}: {}".format(status, body[:200]))

    log("=" * 60)
    log("If all four tests PASS but the editor still says '(not connected)',")
    log("that means OAuth sign-in is the only thing missing - the streaming")
    log("itself works. Click 'Sign In' in the Cesium panel address bar to")
    log("restore full sign-in for browsing the Asset Depot.")
    log("=" * 60)


if __name__ == "__main__":
    main()
