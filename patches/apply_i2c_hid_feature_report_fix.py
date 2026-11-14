from pathlib import Path

source = Path("src/add-ons/kernel/drivers/input/i2c_hid/HIDDevice.cpp")
text = source.read_text()

def replace_exact(old, new, expected=1):
    global text
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"Refusing to patch: expected {expected} occurrence(s), found {count}: {old!r}")
    text = text.replace(old, new)

replace_exact(
    "#define HID_USAGE_MICROSOFT_THQA_CERTIFICATE 0xC5",
    "#define HID_USAGE_MICROSOFT_THQA_CERTIFICATE 0xC5\n"
    "\n// I2C-HID GET_REPORT encodes Feature as 3 (wire value).\n"
    "#define I2C_HID_REPORT_TYPE_FEATURE 0x03"
)
replace_exact(
    "\tfTransferBuffer = (uint8 *)malloc(fDescriptor.wMaxInputLength + 3);",
    "\tsize_t transferBufferSize = fDescriptor.wMaxInputLength;\n"
    "\tif (fTransferBufferSize > transferBufferSize)\n"
    "\t\ttransferBufferSize = fTransferBufferSize;\n"
    "\tfTransferBuffer = (uint8 *)malloc(transferBufferSize + 3);"
)
replace_exact(
    "\t\t\tstatus_t result = MaybeScheduleTransfer(report);",
    "\t\t\tstatus_t result = _FetchReport(I2C_HID_REPORT_TYPE_FEATURE,\n"
    "\t\t\t\treport->ID(), report->ReportSize());",
    expected=3
)

source.write_text(text)
print("Feature-report fix applied; all 5 exact replacements verified.")
