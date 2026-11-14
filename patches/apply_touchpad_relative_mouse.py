#!/usr/bin/env python3
"""Add a touchpad-only absolute-to-relative mouse protocol path.

The patch is deliberately restricted to HID Digitizer/Touch Pad application
collections. Touchscreens and pen/tablet collections retain the existing
absolute tablet interface.
"""
from pathlib import Path
import subprocess

EXPECTED_COMMIT = "4aae8640c9b3d021cb568a514adbc1e2f48c7912"
actual_commit = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], universal_newlines=True
).strip()
if actual_commit != EXPECTED_COMMIT:
    raise SystemExit("Refusing unexpected Haiku source revision: " + actual_commit)

header = Path("src/add-ons/kernel/drivers/input/hid_shared/TabletProtocolHandler.h")
source = Path("src/add-ons/kernel/drivers/input/hid_shared/TabletProtocolHandler.cpp")
h = header.read_text(encoding="utf-8")
c = source.read_text(encoding="utf-8")

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, got {count}")
    return text.replace(old, new)

h = replace_once(
    h,
    "TabletProtocolHandler(HIDReport &report,\n\t\t\t\t\t\t\t\t\tHIDReportItem &xAxis,\n\t\t\t\t\t\t\t\t\tHIDReportItem &yAxis);",
    "TabletProtocolHandler(HIDReport &report,\n\t\t\t\t\t\t\t\t\tHIDReportItem &xAxis,\n\t\t\t\t\t\t\t\t\tHIDReportItem &yAxis,\n\t\t\t\t\t\t\t\t\tbool isTouchpad);",
    "constructor declaration",
)
h = replace_once(
    h,
    "\t\t\tHIDReport &\t\t\tfReport;\n",
    "\t\t\tHIDReport &\t\t\tfReport;\n"
    "\n\t\t\tbool\t\t\t\t\tfIsTouchpad;\n"
    "\t\t\tfloat\t\t\t\t\tfLastX;\n"
    "\t\t\tfloat\t\t\t\t\tfLastY;\n"
    "\t\t\tbool\t\t\t\t\tfHasLastPosition;\n",
    "touchpad state fields",
)

c = replace_once(
    c,
    "TabletProtocolHandler::TabletProtocolHandler(HIDReport &report,\n"
    "\tHIDReportItem &xAxis, HIDReportItem &yAxis)",
    "TabletProtocolHandler::TabletProtocolHandler(HIDReport &report,\n"
    "\tHIDReportItem &xAxis, HIDReportItem &yAxis, bool isTouchpad)",
    "constructor definition",
)
c = replace_once(
    c,
    "\tProtocolHandler(report.Device(), \"input/tablet/\" DEVICE_PATH_SUFFIX \"/\",\n"
    "\t\t0),\n"
    "\tfReport(report),\n",
    "\tProtocolHandler(report.Device(), isTouchpad\n"
    "\t\t? \"input/mouse/\" DEVICE_PATH_SUFFIX \"/\"\n"
    "\t\t: \"input/tablet/\" DEVICE_PATH_SUFFIX \"/\", 0),\n"
    "\tfReport(report),\n"
    "\tfIsTouchpad(isTouchpad),\n"
    "\tfLastX(0.0f),\n"
    "\tfLastY(0.0f),\n"
    "\tfHasLastPosition(false),\n",
    "constructor initialization",
)
c = replace_once(
    c,
    "\t\tProtocolHandler *newHandler = new(std::nothrow) TabletProtocolHandler(\n"
    "\t\t\t*inputReport, *xAxis, *yAxis);",
    "\t\tbool isTouchpad = collection.UsagePage() == B_HID_USAGE_PAGE_DIGITIZER\n"
    "\t\t\t&& collection.UsageID() == B_HID_UID_DIG_TOUCH_PAD;\n"
    "\t\tProtocolHandler *newHandler = new(std::nothrow) TabletProtocolHandler(\n"
    "\t\t\t*inputReport, *xAxis, *yAxis, isTouchpad);",
    "touchpad-specific construction",
)

c = replace_once(
    c,
    "\t\t\tconst char name[] = DEVICE_NAME\" Tablet\";\n"
    "\t\t\treturn IOGetDeviceName(name,buffer,length);",
    "\t\t\tconst char *name = fIsTouchpad\n"
    "\t\t\t\t? DEVICE_NAME\" Touchpad Mouse\" : DEVICE_NAME\" Tablet\";\n"
    "\t\t\treturn IOGetDeviceName(name, buffer, length);",
    "device name",
)

old_read = """\t\tcase MS_READ:
\t\t{
\t\t\tif (length < sizeof(tablet_movement))
\t\t\t\treturn B_BUFFER_OVERFLOW;

\t\t\twhile (true) {
\t\t\t\ttablet_movement movement;
\t\t\t\tstatus_t result = _ReadReport(&movement, cookie);
\t\t\t\tif (result == B_INTERRUPTED)
\t\t\t\t\treturn result;
\t\t\t\tif (result == B_BUSY)
\t\t\t\t\tcontinue;

\t\t\t\tif (!IS_USER_ADDRESS(buffer)
\t\t\t\t\t|| user_memcpy(buffer, &movement, sizeof(movement))
\t\t\t\t\t\t!= B_OK) {
\t\t\t\t\treturn B_BAD_ADDRESS;
\t\t\t\t}

\t\t\t\treturn result;
\t\t\t}
\t\t}
"""
new_read = """\t\tcase MS_READ:
\t\t{
\t\t\tunion {
\t\t\t\tmouse_movement mouse;
\t\t\t\ttablet_movement tablet;
\t\t\t} movement;
\t\t\tsize_t movementSize = fIsTouchpad
\t\t\t\t? sizeof(mouse_movement) : sizeof(tablet_movement);
\t\t\tif (length < movementSize)
\t\t\t\treturn B_BUFFER_OVERFLOW;

\t\t\twhile (true) {
\t\t\t\tstatus_t result = _ReadReport(&movement, cookie);
\t\t\t\tif (result == B_INTERRUPTED)
\t\t\t\t\treturn result;
\t\t\t\tif (result == B_BUSY)
\t\t\t\t\tcontinue;

\t\t\t\tif (!IS_USER_ADDRESS(buffer)
\t\t\t\t\t|| user_memcpy(buffer, &movement, movementSize) != B_OK) {
\t\t\t\t\treturn B_BAD_ADDRESS;
\t\t\t\t}

\t\t\t\treturn result;
\t\t\t}
\t\t}
"""
c = replace_once(c, old_read, new_read, "MS_READ dual output")

old_end = """\ttablet_movement *info = (tablet_movement *)buffer;
\tmemset(info, 0, sizeof(tablet_movement));

\tinfo->xpos = axisAbsoluteData[0];
\tinfo->ypos = axisAbsoluteData[1];
\tinfo->has_contact = inRange;
\tinfo->pressure = pressure;
\tinfo->tilt_x = xTilt;
\tinfo->tilt_y = yTilt;

\tinfo->switches = switches;
\tinfo->buttons = buttons;
\tinfo->clicks = clicks;
\tinfo->timestamp = timestamp;
\tinfo->wheel_ydelta = -wheelData;

\treturn B_OK;
"""
new_end = """\tif (fIsTouchpad) {
\t\t// HID Touch Pad coordinates are absolute. Convert consecutive samples
\t\t// into relative mouse deltas, and discard the first sample after every
\t\t// contact start so lifting/repositioning a finger cannot move the cursor.
\t\tbool hasContact = (switches & B_TIP_SWITCH) != 0;
\t\tmouse_movement *info = (mouse_movement *)buffer;
\t\tmemset(info, 0, sizeof(mouse_movement));

\t\tif (hasContact) {
\t\t\tif (fHasLastPosition) {
\t\t\t\t// Normalized HID surface coordinates mapped to a practical
\t\t\t\t// pointer travel scale. Y increases downwards on absolute pads.
\t\t\t\tinfo->xdelta = (int32)((axisAbsoluteData[0] - fLastX) * 1800.0f);
\t\t\t\tinfo->ydelta = (int32)((axisAbsoluteData[1] - fLastY) * 1000.0f);
\t\t\t}
\t\t\tfLastX = axisAbsoluteData[0];
\t\t\tfLastY = axisAbsoluteData[1];
\t\t\tfHasLastPosition = true;
\t\t} else {
\t\t\tfHasLastPosition = false;
\t\t}

\t\tinfo->buttons = buttons;
\t\tinfo->clicks = clicks;
\t\tinfo->timestamp = timestamp;
\t\tinfo->wheel_ydelta = -wheelData;
\t\treturn B_OK;
\t}

\ttablet_movement *info = (tablet_movement *)buffer;
\tmemset(info, 0, sizeof(tablet_movement));

\tinfo->xpos = axisAbsoluteData[0];
\tinfo->ypos = axisAbsoluteData[1];
\tinfo->has_contact = inRange;
\tinfo->pressure = pressure;
\tinfo->tilt_x = xTilt;
\tinfo->tilt_y = yTilt;

\tinfo->switches = switches;
\tinfo->buttons = buttons;
\tinfo->clicks = clicks;
\tinfo->timestamp = timestamp;
\tinfo->wheel_ydelta = -wheelData;

\treturn B_OK;
"""
c = replace_once(c, old_end, new_end, "relative conversion output")

header.write_text(h, encoding="utf-8")
source.write_text(c, encoding="utf-8")
print("Applied touchpad-only absolute-to-relative mouse conversion.")
