#!/usr/bin/env python3
from pathlib import Path
import subprocess

EXPECTED_COMMIT = "4aae8640c9b3d021cb568a514adbc1e2f48c7912"
actual_commit = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], universal_newlines=True
).strip()
if actual_commit != EXPECTED_COMMIT:
    raise SystemExit(
        "Refusing to patch unexpected Haiku source revision: " + actual_commit
    )

paths = {
    "i2c": Path("src/add-ons/kernel/drivers/input/i2c_hid/HIDDevice.cpp"),
    "parser": Path("src/add-ons/kernel/drivers/input/hid_shared/HIDParser.cpp"),
    "parser_header": Path("src/add-ons/kernel/drivers/input/hid_shared/HIDParser.h"),
    "usb": Path("src/add-ons/kernel/drivers/input/usb_hid/HIDDevice.cpp"),
    "hyperv": Path("src/add-ons/kernel/drivers/input/hyperv/hid/HIDDevice.cpp"),
}
texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}


def replace_exact(name, old, new, expected=1):
    text = texts[name]
    count = text.count(old)
    if count != expected:
        raise SystemExit(
            f"Refusing partial patch in {paths[name]}: "
            f"expected {expected} exact match(es), found {count}"
        )
    texts[name] = text.replace(old, new)


def replace_between(name, start, end, replacement):
    text = texts[name]
    if text.count(start) != 1 or text.count(end) != 1:
        raise SystemExit(
            f"Refusing partial patch in {paths[name]}: "
            "function boundary did not match exactly once"
        )
    start_at = text.index(start)
    end_at = text.index(end, start_at)
    if end_at < start_at:
        raise SystemExit(f"Invalid function boundaries in {paths[name]}")
    texts[name] = text[:start_at] + replacement + text[end_at:]


# The shared parser must route Input and Feature reports independently.
replace_exact(
    "parser_header",
    "\t\tvoid\t\t\t\t\tSetReport(status_t status, uint8 *report,\n"
    "\t\t\t\t\t\t\t\t\tsize_t length);",
    "\t\tvoid\t\t\t\t\tSetReport(status_t status, uint8 *report,\n"
    "\t\t\t\t\t\t\t\t\tsize_t length, uint8 type);",
)

replace_between(
    "parser",
    "void\nHIDParser::SetReport(status_t status, uint8 *report, size_t length)\n{",
    "\n\nvoid\nHIDParser::PrintToStream()",
    """void
HIDParser::SetReport(status_t status, uint8 *report, size_t length, uint8 type)
{
\tif (status != B_OK || length == 0) {
\t\tif (status == B_OK)
\t\t\tstatus = B_ERROR;

\t\treport = NULL;
\t\tlength = 0;
\t}

\tuint8 targetID = 0;
\tif (fUsesReportIDs && status == B_OK) {
\t\ttargetID = report[0];
\t\treport++;
\t\tlength--;
\t}

\t// Notify all reports of the requested type, as we don't know which
\t// report has waiting listeners. Reports with other IDs need to retry.
\tfor (int32 i = 0; i < fReports.Count(); i++) {
\t\tif (fReports[i] == NULL || fReports[i]->Type() != type)
\t\t\tcontinue;

\t\tif (fReports[i]->ID() == targetID)
\t\t\tfReports[i]->SetReport(status, report, length);
\t\telse
\t\t\tfReports[i]->SetReport(B_BUSY, NULL, 0);
\t}
}""".replace("\\t", "\t"),
)

# Size the shared buffer for the largest GET_REPORT response, including its
# two-byte I2C-HID length prefix and HIDReportItem's three padding bytes.
replace_exact(
    "i2c",
    "#define HID_USAGE_MICROSOFT_THQA_CERTIFICATE 0xC5",
    "#define HID_USAGE_MICROSOFT_THQA_CERTIFICATE 0xC5\n"
    "\n// I2C-HID GET_REPORT uses wire report type 3 for Feature reports.\n"
    "#define I2C_HID_REPORT_TYPE_FEATURE 0x03",
)
replace_exact(
    "i2c",
    "\t// We pad the allocation size so that we can always read 32 bits at a time\n"
    "\t// (as done in HIDReportItem) without the need for an additional boundary\n"
    "\t// check. We don't increase the transfer buffer size though as to not expose\n"
    "\t// this implementation detail onto the device when scheduling transfers.\n"
    "\tfTransferBuffer = (uint8 *)malloc(fDescriptor.wMaxInputLength + 3);",
    "\t// Input reports include the two-byte I2C-HID length prefix. Feature reports\n"
    "\t// fetched with GET_REPORT can be larger than wMaxInputLength.\n"
    "\tsize_t transferBufferSize = fDescriptor.wMaxInputLength;\n"
    "\tsize_t featureBufferSize = fTransferBufferSize + 2;\n"
    "\tif (featureBufferSize > transferBufferSize)\n"
    "\t\ttransferBufferSize = featureBufferSize;\n"
    "\n"
    "\t// Keep three padding bytes for HIDReportItem's 32-bit reads.\n"
    "\tfTransferBuffer = (uint8 *)malloc(transferBufferSize + 3);",
)

# These are Feature Reports, not data from the Input Register.
replace_exact(
    "i2c",
    "\t\t\tstatus_t result = MaybeScheduleTransfer(report);",
    "\t\t\tstatus_t result = _FetchReport(I2C_HID_REPORT_TYPE_FEATURE,\n"
    "\t\t\t\treport->ID(), report->ReportSize());",
    expected=3,
)

# DoneProcessing() is paired with WaitForReport(); these constructor-time
# synchronous GET_REPORT calls never increment fBusyCount.
replace_exact("i2c", "\t\t\t\treport->DoneProcessing();\n", "", expected=2)
replace_exact("i2c", "\t\t\treport->DoneProcessing();\n", "", expected=1)

# Input-register transfers must only update Input reports.
replace_exact(
    "i2c",
    "\tfParser.SetReport(status,\n"
    "\t\t(uint8*)((addr_t)fTransferBuffer + 2), actualLength);",
    "\tfParser.SetReport(status,\n"
    "\t\t(uint8*)((addr_t)fTransferBuffer + 2), actualLength, HID_REPORT_TYPE_INPUT);",
)
replace_exact(
    "i2c",
    "\tdevice->fParser.SetReport(status, device->fTransferBuffer, actualLength);",
    "\tdevice->fParser.SetReport(status, device->fTransferBuffer, actualLength,\n"
    "\t\tHID_REPORT_TYPE_INPUT);",
)

# Fetch Feature reports through GET_REPORT, validate the returned length and ID,
# and keep the wire report type distinct from HID_REPORT_TYPE_FEATURE's bitmask.
replace_between(
    "i2c",
    "status_t\nHIDDevice::_FetchReport(uint8 type, uint8 id, size_t reportSize)\n{",
    "\n\nstatus_t\nHIDDevice::_FetchBuffer",
    """status_t
HIDDevice::_FetchReport(uint8 type, uint8 id, size_t reportSize)
{
\tif (fRemoved)
\t\treturn ENODEV;

\tif (atomic_get_and_set(&fTransferScheduled, 1) != 0)
\t\treturn B_BUSY;

\tuint8 reportId = id > 15 ? 15 : id;
\tsize_t cmdLength = 6;
\tuint8 cmd[] = {
\t\t(uint8)(fDescriptor.wCommandRegister & 0xff),
\t\t(uint8)(fDescriptor.wCommandRegister >> 8),
\t\t(uint8)(reportId | (type << 4)),
\t\tI2C_HID_CMD_GET_REPORT,
\t\t0, 0, 0,
\t};

\tint dataOffset = 4;
\tif (reportId == 15) {
\t\tcmd[dataOffset++] = id;
\t\tcmdLength++;
\t}
\tcmd[dataOffset++] = fDescriptor.wDataRegister & 0xff;
\tcmd[dataOffset++] = fDescriptor.wDataRegister >> 8;

\t// The report ID is present in the response only when report IDs are used.
\tsize_t reportIdLength = fParser.UsesReportIDs() ? 1 : 0;
\tsize_t bufferLength = reportSize + reportIdLength + 2;

\tstatus_t status = _FetchBuffer(cmd, cmdLength, fTransferBuffer,
\t\tbufferLength);
\tif (status != B_OK) {
\t\tatomic_set(&fTransferScheduled, 0);
\t\treturn status;
\t}

\tuint16 actualLength = fTransferBuffer[0] | (fTransferBuffer[1] << 8);
\tTRACE("_FetchReport %" B_PRIuSIZE " %" B_PRIu16 "\\n", reportSize,
\t\tactualLength);

\tif (actualLength <= 2 || actualLength == 0xffff) {
\t\tatomic_set(&fTransferScheduled, 0);
\t\treturn B_BAD_DATA;
\t}

\tsize_t payloadLength = actualLength - 2;
\tif (payloadLength > bufferLength - 2)
\t\tpayloadLength = bufferLength - 2;

\tsize_t expectedLength = reportSize + reportIdLength;
\tif (payloadLength < expectedLength
\t\t|| (reportIdLength != 0 && fTransferBuffer[2] != id)) {
\t\tatomic_set(&fTransferScheduled, 0);
\t\treturn B_BAD_DATA;
\t}

\tatomic_set(&fTransferScheduled, 0);
\tfParser.SetReport(B_OK, fTransferBuffer + 2, payloadLength,
\t\tHID_REPORT_TYPE_FEATURE);
\treturn B_OK;
}""".replace("\\t", "\t"),
)

# The other transports deliver Input reports only.
replace_exact(
    "usb",
    "\tdevice->fParser.SetReport(status, device->fTransferBuffer, actualLength);",
    "\tdevice->fParser.SetReport(status, device->fTransferBuffer, actualLength,\n"
    "\t\tHID_REPORT_TYPE_INPUT);",
)
replace_exact(
    "hyperv",
    "\tfParser.SetReport(B_OK, reportMessage->data, reportMessage->header.length);",
    "\tfParser.SetReport(B_OK, reportMessage->data, reportMessage->header.length,\n"
    "\t\tHID_REPORT_TYPE_INPUT);",
)

if "report->DoneProcessing();" in texts["i2c"]:
    raise SystemExit("Unexpected constructor DoneProcessing() remains")

# All validations passed. Only now write the modified source files.
for name, path in paths.items():
    path.write_text(texts[name], encoding="utf-8")

print("Applied the type-safe I2C-HID Feature Report fix.")
print("Verified exact source revision and every replacement count.")
