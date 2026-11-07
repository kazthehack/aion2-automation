# test_interception.py
from ctypes import WinDLL, c_void_p, c_int, byref
from ctypes import Structure, c_ushort, c_uint
import time
import os
lib_path = os.path.join(os.path.dirname(__file__), 'Interception', 'library', 'x64', 'interception.dll')
print("Loading", lib_path)
lib = WinDLL(lib_path)

# Declare function prototypes for safer ctypes conversions
lib.interception_create_context.restype = c_void_p
lib.interception_destroy_context.argtypes = [c_void_p]
lib.interception_send.restype = c_int
lib.interception_send.argtypes = [c_void_p, c_int, c_void_p, c_uint]
lib.interception_is_keyboard.argtypes = [c_int]
lib.interception_is_mouse.argtypes = [c_int]

# minimal restype/arg declarations
lib.interception_create_context.restype = c_void_p
lib.interception_destroy_context.argtypes = [c_void_p]
lib.interception_is_keyboard.argtypes = [c_int]
lib.interception_is_mouse.argtypes = [c_int]

ctx = lib.interception_create_context()
if not ctx:
    raise SystemExit("Failed to create interception context (driver missing or not installed)")

print("Context created:", bool(ctx))

# enumerate first 32 device slots and print whether they claim to be keyboard/mouse
print("Enumerating device slots (0-31):")
for dev in range(32):
    try:
        k = lib.interception_is_keyboard(dev)
        m = lib.interception_is_mouse(dev)
        if k or m:
            print(f"  device {dev}: keyboard={bool(k)} mouse={bool(m)}")
    except Exception as e:
        print("  device", dev, "error:", e)

# OPTIONAL: simple send test (scancode for 'a') - only run if comfortable
# from input_controller.py the code maps VK->scancode via MapVirtualKey
# The snippet below constructs the same minimal structure and calls interception_send.
class Stroke(Structure):
    _fields_ = [('code', c_ushort), ('state', c_ushort), ('information', c_uint)]

# Example: send 'a' using VK code 0x41 -> translate to scancode via MapVirtualKey (we'll use MapVirtualKeyW)
import ctypes
user32 = ctypes.windll.user32
VK_A = 0x41
sc = user32.MapVirtualKeyW(VK_A, 0)
down = Stroke(code=sc, state=0, information=0)
up   = Stroke(code=sc, state=1, information=0)

print("Sending 'a' down/up to focused window (Notepad). Switch focus to Notepad now.")
time.sleep(3)
try:
    # Call with properly-typed args (ctx is c_void_p due to restype)
    res = lib.interception_send(ctx, 1, byref(down), 1)  # device 1 is typical for keyboard mapping in many setups
    print("send down res:", res)
except Exception as e:
    print("interception_send error:", e)
time.sleep(0.05)
try:
    res = lib.interception_send(ctx, 1, byref(up), 1)
    print("send up res:", res)
except Exception as e:
    print("interception_send error:", e)

lib.interception_destroy_context(ctx)
print("Done")