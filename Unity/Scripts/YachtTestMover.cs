using UnityEngine;
using UnityEngine.InputSystem;

public class YachtTestMover : MonoBehaviour
{
    public float moveSpeed = 5f;
    public float turnSpeed = 60f;

    void Update()
    {
        if (Keyboard.current == null) return;

        float move = 0f;
        float turn = 0f;

        if (Keyboard.current.wKey.isPressed) move = 1f;
        if (Keyboard.current.sKey.isPressed) move = -1f;
        if (Keyboard.current.aKey.isPressed) turn = -1f;
        if (Keyboard.current.dKey.isPressed) turn = 1f;

        transform.Rotate(0f, turn * turnSpeed * Time.deltaTime, 0f, Space.World);
        transform.Translate(0f, 0f, move * moveSpeed * Time.deltaTime, Space.Self);
    }
}