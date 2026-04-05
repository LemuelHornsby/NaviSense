using UnityEngine;
using UnityEngine.InputSystem;

public class CameraModeController : MonoBehaviour
{
    public enum CameraMode
    {
        Follow,
        Overhead,
        DockingView
    }

    [Header("Target")]
    public Transform target;

    [Header("Starting Mode")]
    public CameraMode currentMode = CameraMode.Follow;

    [Header("Smoothing")]
    public float positionSmoothTime = 0.25f;
    public float rotationSmoothSpeed = 5f;

    [Header("Zoom")]
    public bool enableZoom = true;
    public float zoomSpeed = 0.05f;

    [Header("Follow View")]
    public Vector3 followOffset = new Vector3(0f, 8f, -18f);
    public Vector3 followEuler = new Vector3(15f, 0f, 0f);
    public float followMinDistance = 10f;
    public float followMaxDistance = 30f;

    [Header("Overhead View")]
    public Vector3 overheadOffset = new Vector3(0f, 35f, 0f);
    public Vector3 overheadEuler = new Vector3(90f, 0f, 0f);
    public float overheadMinHeight = 15f;
    public float overheadMaxHeight = 60f;

    [Header("Docking View")]
    public Vector3 dockingOffset = new Vector3(2f, 5f, -10f);
    public Vector3 dockingEuler = new Vector3(12f, 0f, 0f);
    public float dockingMinDistance = 5f;
    public float dockingMaxDistance = 16f;

    [Header("UI")]
    public bool showModeLabel = true;

    private Vector3 velocity;

    void Update()
    {
        if (target == null) return;

        HandleModeSwitch();
        if (enableZoom) HandleZoom();
    }

    void LateUpdate()
    {
        if (target == null) return;

        Quaternion targetYaw = Quaternion.Euler(0f, target.eulerAngles.y, 0f);

        Vector3 localOffset;
        Vector3 localEuler;
        Vector3 desiredPosition;
        Quaternion desiredRotation;

        switch (currentMode)
        {
            case CameraMode.Overhead:
                localOffset = overheadOffset;
                localEuler = overheadEuler;
                desiredPosition = target.position + localOffset;
                desiredRotation = Quaternion.Euler(localEuler);
                break;

            case CameraMode.DockingView:
                localOffset = dockingOffset;
                localEuler = dockingEuler;
                desiredPosition = target.position + targetYaw * localOffset;
                desiredRotation = Quaternion.Euler(
                    localEuler.x,
                    target.eulerAngles.y + localEuler.y,
                    localEuler.z
                );
                break;

            default:
                localOffset = followOffset;
                localEuler = followEuler;
                desiredPosition = target.position + targetYaw * localOffset;
                desiredRotation = Quaternion.Euler(
                    localEuler.x,
                    target.eulerAngles.y + localEuler.y,
                    localEuler.z
                );
                break;
        }

        transform.position = Vector3.SmoothDamp(
            transform.position,
            desiredPosition,
            ref velocity,
            positionSmoothTime
        );

        transform.rotation = Quaternion.Slerp(
            transform.rotation,
            desiredRotation,
            rotationSmoothSpeed * Time.deltaTime
        );
    }

    void HandleModeSwitch()
    {
        if (Keyboard.current == null) return;

        if (Keyboard.current.digit1Key.wasPressedThisFrame)
            currentMode = CameraMode.Follow;

        if (Keyboard.current.digit2Key.wasPressedThisFrame)
            currentMode = CameraMode.Overhead;

        if (Keyboard.current.digit3Key.wasPressedThisFrame)
            currentMode = CameraMode.DockingView;
    }

    void HandleZoom()
    {
        if (Mouse.current == null) return;

        float scroll = Mouse.current.scroll.ReadValue().y;
        if (Mathf.Abs(scroll) < 0.01f) return;

        switch (currentMode)
        {
            case CameraMode.Overhead:
                overheadOffset.y -= scroll * zoomSpeed;
                overheadOffset.y = Mathf.Clamp(overheadOffset.y, overheadMinHeight, overheadMaxHeight);
                break;

            case CameraMode.DockingView:
                dockingOffset.z += scroll * zoomSpeed;
                dockingOffset.z = Mathf.Clamp(dockingOffset.z, -dockingMaxDistance, -dockingMinDistance);
                break;

            default:
                followOffset.z += scroll * zoomSpeed;
                followOffset.z = Mathf.Clamp(followOffset.z, -followMaxDistance, -followMinDistance);
                break;
        }
    }

    void OnGUI()
    {
        if (!showModeLabel) return;

        GUIStyle style = new GUIStyle(GUI.skin.box);
        style.fontSize = 18;
        style.alignment = TextAnchor.MiddleCenter;

        string label = "Camera Mode: " + currentMode + "   [1 Follow] [2 Overhead] [3 Docking]";
        GUI.Box(new Rect(10, 10, 430, 32), label, style);
    }
}