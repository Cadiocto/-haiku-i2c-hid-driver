# Haiku I2C-HID driver experiment

This repository contains a **proposed, unvalidated** patch for Haiku's I2C-HID driver and a GitHub Actions workflow that attempts to build the addon inside a Haiku R1/beta6 x86_64 virtual machine.

## Contents

- `patches/i2c_hid_feature_report_fix.patch` — changes the initial retrieval of I2C-HID Feature reports to use the I2C-HID `GET_REPORT` command, and sizes the shared transfer buffer for the largest parsed report.
- `.github/workflows/haiku-i2c-hid-build.yml` — checks the patch against the current upstream Haiku source and attempts to compile the `i2c_hid` kernel addon in Haiku VM using `vmactions/haiku-vm`.

## Run the build

1. Open the **Actions** tab.
2. Select **Haiku I2C-HID driver build**.
3. Choose **Run workflow**.

The workflow also runs on pushes that change the patch or workflow file. If successful, it uploads an artifact named `haiku-i2c-hid-x86_64`.

## Important limitations

- This is an experimental patch, not a confirmed fix. A successful compile only proves that the code builds; it does not prove the touchpad works.
- The workflow builds against the current default branch of `haiku/haiku`, not the exact local revision `hrev60072+631`. Exact-revision compatibility still needs to be checked.
- The VM runs under QEMU. It cannot test the physical I2C controller or the touchpad in the Chuwi MiniBook X.
- Do not install the resulting addon over the system driver without keeping a recovery path (for example, a bootable Haiku USB and a backup of the original addon).

## Upstream references

- [Haiku source](https://github.com/haiku/haiku)
- [Haiku VM GitHub Action](https://github.com/vmactions/haiku-vm)
