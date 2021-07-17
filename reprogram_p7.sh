#!/usr/bin/bash

DIALOG_WORKSPACE="/c/hh/dialog_14683_scratch"

CURRENT_DIR=`pwd`
APP_BIN="${CURRENT_DIR}/freertos_retarget.bin"
BL_BIN="${CURRENT_DIR}/ble_suota_loader.bin"
BL_UTILS_PATH="${DIALOG_WORKSPACE}/utilities/scripts/qspi"
HPY_UTILS_PATH="${DIALOG_WORKSPACE}/utilities/scripts/hpy/v11"
# Example command
#./program_qspi_jtag.bat --jlink_path "c:\Program Files (x86)\SEGGER\JLink_V612i" \
# "C:\Dialog_Workspaces\Dialog_FreeRTOS_01\sdk\bsp\system\loaders\ble_suota_loader\DA14683-00-Release_QSPI\ble_suota_loader.bin"
pushd "${BL_UTILS_PATH}"
./program_qspi_jtag.bat --jlink_path "c:\Program Files (x86)\SEGGER\JLink_V612i" "${BL_BIN}s" || exit 1
popd
# Example command
#./initial_flash.bat --jlink_path "c:\Program Files (x86)\SEGGER\JLink_V612i" \
# "C:\Dialog_Workspaces\Dialog_FreeRTOS_01\projects\dk_apps\templates\freertos_retarget\Happy_P6_QSPI_Debug\freertos_retarget.bin"
pushd "${HPY_UTILS_PATH}"
./initial_flash.bat --jlink_path "c:\Program Files (x86)\SEGGER\JLink_V612i" "${APP_BIN}" || exit 2
popd