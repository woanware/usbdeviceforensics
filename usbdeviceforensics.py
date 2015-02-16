#!/usr/bin/python

# This file is part of usbdeviceforensics. usbdeviceforensics is a python console based port of woanware's
# UsbDeviceForensics .Net WinForms GUI application.
#
# Copyright 2014 Mark Woan <markwoan[@]gmail.com>

import argparse
import os
from Registry import *
import traceback
import sys
import binascii
import struct
from enum import Enum
from datetime import datetime, timedelta
from pytz import timezone
import pytz
import re
import csv

# Enums #######################################################################

class WindowsVersions(Enum):
    """Enum to aid the detection of Windows in-use"""
    NotDefined      = ""
    Windows2000     = "5.0"
    WindowsXP       = "5.1"
    WindowsXPx64    = "5.2"
    Windows2k3      = "5.2"
    Windows2k3R2    = "5.2"
    WindowsVista    = "6.0"
    Windows2008     = "6.0"
    Windows2008R2   = "6.1"
    Windows7        = "6.1"
    Windows2012     = "6.2"
    Windows8        = "6.2"
    Windows2012R2   = "6.3"
    Windows8        = "6.3"
    Windows10       = "6.4"

# Variables ###################################################################

usb_devices = []
debug_mode = True
os_version = WindowsVersions.NotDefined

# Objects #####################################################################

class EmdMgmt():
    """Encapsulates the EmdMgmt registry key values"""
    def __init__(self):
        self.volume_serial_num = 0
        self.volume_serial_num_hex = ''
        self.volume_name = ''
        self.timestamp = datetime.min


class MountPoint2():
    """Encapsulates the MountPoint2 registry key values"""
    def __init__(self):
        self.timestamp = datetime.min
        self.file = ''


class UsbDevice():
    """Encapsulates a single USB device"""
    def __init__(self):
        self.vendor = ''
        self.product = ''
        self.version = ''
        self.serial_number = ''
        self.vid = ''
        self.pid = ''
        self.parent_prefix_id = ''
        self.drive_letter = ''
        self.volume_name = ''
        self.guid = ''
        self.disk_signature = ''
        self.mountpoint = ''
        self.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b = datetime.min
        self.device_classes_datetime_10497b1bba5144e58318a65c837b6661 = datetime.min
        self.vid_pid_datetime = datetime.min
        self.usb_stor_datetime = datetime.min
        self.install_datetime = datetime.min
        self.usbstor_datetime64 = datetime.min
        self.usbstor_datetime65 = datetime.min
        self.usbstor_datetime66 = datetime.min
        self.usbstor_datetime67 = datetime.min
        self.mountpoint2 = []
        self.emdmgmt = []


# System Hive Methods #########################################################

def process(registry_path, output, format):
    """Processing entry point"""

    # Process the hives in a specific order so that the
    # data can be correctly matched between the hives
    process_registry_hive(registry_path, Registry.HiveType.SYSTEM)
    process_registry_hive(registry_path, Registry.HiveType.SOFTWARE)
    process_registry_hive(registry_path, Registry.HiveType.NTUSER)

    # Loop through the files looking for the *.log files
    for root, dirs, files in os.walk(registry_path):
        for f in files:
            try:
                file_name, ext = os.path.splitext(f)
                if ext.lower() != ".log":
                    continue

                process_log_file(os.path.join(root, f))

            except Exception as err:
                traceback.print_exc(file=sys.stdout)
                traceback.print_stack()
                print(err.args)
                print(err.message)

    output_data_to_console()

    if output is None:
        return

    if format == "csv":
        output_data_to_file_csv(output)
    else:
        output_data_to_file_text(output)

def process_registry_hive(registry_path, hive_type):
    """Generic method used to process a single registry hive type"""
    for root, dirs, files in os.walk(registry_path):
        for f in files:
            try:
                registry = load_file(os.path.join(root, f))
                if registry is None:
                    continue

                if registry.hive_type() == Registry.HiveType.SYSTEM and hive_type == Registry.HiveType.SYSTEM:
                    print('Hive name: ' + registry.hive_name())
                    print('Hive type: ' + registry.hive_type().value)
                    process_usb_stor(registry)
                    process_usb_stor_properties(registry)
                    process_usb(registry)
                    process_mounted_devices(registry)
                    process_device_classes(registry)

                if registry.hive_type() == Registry.HiveType.SOFTWARE and hive_type == Registry.HiveType.SOFTWARE:
                    print('Hive name: ' + registry.hive_name())
                    print('Hive type: ' + registry.hive_type().value)
                    get_os_version(registry)
                    process_windows_portable_devices(registry)
                    process_emd_mgmt(registry)

                if registry.hive_type() == Registry.HiveType.NTUSER and hive_type == Registry.HiveType.NTUSER:
                    print('Hive name: ' + registry.hive_name())
                    print('Hive type: ' + registry.hive_type().value)
                    process_mountpoints2(registry, f)

            except Exception as err:
                traceback.print_exc(file=sys.stdout)
                traceback.print_stack()
                print(err.args)
                print(err.message)


def output_data_to_console():
    """Outputs the data to StdOut and an output file if required"""
    for device in usb_devices:
        print("Vendor: " + device.vendor)
        print("Product: " + device.product)
        print("Version: " + device.version)
        print("Serial Number: " + device.serial_number)
        print("VID: " + device.vid)
        print("PID: " + device.pid)
        print("Parent Prefix ID: " + device.parent_prefix_id)
        print("Drive Letter: " + device.drive_letter)
        print("Volume Name: " + device.volume_name)
        print("GUID : " + device.guid)
        print("Mountpoint: " + device.mountpoint)
        print("Disk Signature: " + device.disk_signature)

        if device.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b != datetime.min:
            print("Device Classes Timestamp (53f56): " + device.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b.strftime('%Y-%m-%dT%H:%M:%S'))
        if device.device_classes_datetime_10497b1bba5144e58318a65c837b6661 != datetime.min:
            print("Device Classes Timestamp (10497): " + device.device_classes_datetime_10497b1bba5144e58318a65c837b6661.strftime('%Y-%m-%dT%H:%M:%S'))
        if device.vid_pid_datetime != datetime.min:
            print("VID/PID Timestamp: " + device.vid_pid_datetime.strftime('%Y-%m-%dT%H:%M:%S'))
        if device.usb_stor_datetime != datetime.min:
            print("USBSTOR Timestamp: " + device.usb_stor_datetime.strftime('%Y-%m-%dT%H:%M:%S'))
        if device.install_datetime != datetime.min:
            print("Install Timestamp: " + device.install_datetime.strftime('%Y-%m-%dT%H:%M:%S'))
        if device.usbstor_datetime64 != datetime.min:
            print("USBSTOR Timestamp (64): " + device.usbstor_datetime64.strftime('%Y-%m-%dT%H:%M:%S'))
        if device.usbstor_datetime65 != datetime.min:
            print("USBSTOR Timestamp (65): " + device.usbstor_datetime65.strftime('%Y-%m-%dT%H:%M:%S'))
        if device.usbstor_datetime66 != datetime.min:
            print("USBSTOR Timestamp (66): " + device.usbstor_datetime66.strftime('%Y-%m-%dT%H:%M:%S'))
        if device.usbstor_datetime67 != datetime.min:
            print("USBSTOR Timestamp (67): " + device.usbstor_datetime67.strftime('%Y-%m-%dT%H:%M:%S'))

        for mp in device.mountpoint2:
            print('\tMP2 File: ' + mp.file)
            if mp.timestamp != datetime.min:
                print('\tMP2 Timestamp: ' + mp.timestamp.strftime('%Y-%m-%dT%H:%M:%S'))

        for emd in device.emdmgmt:
            print('\tEMD Volume Serial No.: ' + emd.volume_serial_num)
            print('\tEMD Volume Serial No. (hex): ' + emd.volume_serial_num_hex)
            print('\tEMD Volume Name: ' + emd.volume_name)
            if emd.timestamp != datetime.min:
                print('\tEMD Timestamp: ' + emd.timestamp.strftime('%Y-%m-%dT%H:%M:%S'))

        print('------------------------------------------------------------------------------')


def output_data_to_file_csv(output):
    """Outputs the data to a file in CSV format"""
    write_debug(data='Method: output_data_to_file_csv')

    numMp2 = 0
    for device in usb_devices:
        if len(device.mountpoint2) > numMp2:
            numMp2 = len(device.mountpoint2)

    numEmdMgmt = 0
    for device in usb_devices:
        if len(device.emdmgmt) > numEmdMgmt:
            numEmdMgmt = len(device.emdmgmt)

    write_debug(name='Max Number EmdMgmt', value=str(numEmdMgmt))
    write_debug(name='Max Number MountPoints2', value=str(numMp2))

    with open(output, "wb") as f:
        # Write the CSV headers
        f.write("Vendor\tProduct\tVersion\tSerialNumber\tVID\tPID\tParentIDPrefix\tVolumeName\tGUID\tMountPoint\tInstall\tUSBSTOR\tUSBSTOR Properties (Install Date)\tUSBSTOR Properties (First Install Date)\tUSBSTOR Properties (Last Arrival Date)\tUSBSTOR Properties (Last Removal Date)\tDeviceClasses (53f56307-b6bf-11d0-94f2-00a0c91efb8b)\tDeviceClasses (10497b1b-ba51-44e5-8318-a65c837b6661)\tEnum\\USB VIDPID\t")

        temp = ''
        for i in range(numMp2):
            temp += 'MountPoints2:' + str(i) + '\t'
            temp += 'MountPoints2 File:' + str(i) + '\t'

        if len(temp) > 0:
            # Remove the last comma
            temp = temp[:len(temp)-1]
            f.write(temp)

        temp = ''
        for i in range(numEmdMgmt):
            if i == 0:
                temp += '\t'

            temp += 'EMDMgmt:' + str(i) + '\t'
            temp += 'EMDMgmt Volume Serial No:' + str(i) + '\t'
            temp += 'EMDMgmt Volume Serial No (Hex):' + str(i) + '\t'
            temp += 'EMDMgmt Volume Name:' + str(i) + '\t'

        if len(temp) > 0:
            # Remove the last comma
            temp = temp[:len(temp)-1]
            f.write(temp)

        f.write('\n')

        writer = csv.writer(f, delimiter='\t', quotechar='"', quoting=csv.QUOTE_ALL)
        for device in usb_devices:
            data = []
            data.append(device.vendor)
            data.append(device.product)
            data.append(device.version)
            data.append(device.serial_number)
            data.append(device.vid)
            data.append(device.pid)
            data.append(device.parent_prefix_id)
            data.append(device.volume_name)
            data.append(device.guid)
            data.append(device.mountpoint)
            if device.install_datetime != datetime.min:
                data.append(device.install_datetime)
            if device.usb_stor_datetime != datetime.min:
                data.append(device.usb_stor_datetime)
            if device.usbstor_datetime64 != datetime.min:
                data.append(device.usbstor_datetime64)
            if device.usbstor_datetime65 != datetime.min:
                data.append(device.usbstor_datetime65)
            if device.usbstor_datetime66 != datetime.min:
                data.append(device.usbstor_datetime66)
            if device.usbstor_datetime67 != datetime.min:
                data.append(device.usbstor_datetime67)
            if device.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b != datetime.min:
                data.append(device.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b)
            if device.device_classes_datetime_10497b1bba5144e58318a65c837b6661 != datetime.min:
                data.append(device.device_classes_datetime_10497b1bba5144e58318a65c837b6661)
            if device.vid_pid_datetime != datetime.min:
                data.append(device.vid_pid_datetime)

            for mp in device.mountpoint2:
                if mp.timestamp != datetime.min:
                    data.append(mp.timestamp)
                data.append(mp.file)

            if len(device.mountpoint2) < numMp2:
                for i in range(numMp2 - len(device.mountpoint2)):
                    data.append('')
                    data.append('')

            for em in device.emdmgmt:
                if em.timestamp != datetime.min:
                    data.append(em.timestamp)
                data.append(em.volume_serial_num)
                data.append(em.volume_serial_num_hex)
                data.append(em.volume_name)

            # Balance out the EmdMgmt columns
            if len(device.emdmgmt) < numEmdMgmt:
                for i in range(numEmdMgmt - len(device.emdmgmt)):
                    data.append('')
                    data.append('')
                    data.append('')
                    data.append('')

            writer.writerow(data)


def output_data_to_file_text(output):
    """Outputs the data to a file in text format"""
    write_debug(data='Method: output_data_to_file_text')

    with open(output, "wb") as f:
        for device in usb_devices:
            f.write("Vendor: " + device.vendor + '\n')
            f.write("Product: " + device.product + '\n')
            f.write("Version: " + device.version + '\n')
            f.write("Serial Number: " + device.serial_number + '\n')
            f.write("VID: " + device.vid + '\n')
            f.write("PID: " + device.pid + '\n')
            f.write("Parent Prefix ID: " + device.parent_prefix_id + '\n')
            f.write("Drive Letter: " + device.drive_letter + '\n')
            f.write("Volume Name: " + device.volume_name + '\n')
            f.write("GUID : " + device.guid + '\n')
            f.write("Mountpoint: " + device.mountpoint + '\n')
            f.write("Disk Signature: " + device.disk_signature + '\n')

            if device.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b != datetime.min:
                f.write("Device Classes Timestamp (53f56): " + device.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b.strftime('%Y-%m-%dT%H:%M:%S') + '\n')
            if device.device_classes_datetime_10497b1bba5144e58318a65c837b6661 != datetime.min:
                f.write("Device Classes Timestamp (10497): " + device.device_classes_datetime_10497b1bba5144e58318a65c837b6661.strftime('%Y-%m-%dT%H:%M:%S') + '\n')
            if device.vid_pid_datetime != datetime.min:
                f.write("VID/PID Timestamp: " + device.vid_pid_datetime.strftime('%Y-%m-%dT%H:%M:%S') + '\n')
            if device.usb_stor_datetime != datetime.min:
                f.write("USBSTOR Timestamp: " + device.usb_stor_datetime.strftime('%Y-%m-%dT%H:%M:%S') + '\n')
            if device.install_datetime != datetime.min:
                f.write("Install Timestamp: " + device.install_datetime.strftime('%Y-%m-%dT%H:%M:%S') + '\n')
            if device.usbstor_datetime64 != datetime.min:
                f.write("USBSTOR Timestamp (64): " + device.usbstor_datetime64.strftime('%Y-%m-%dT%H:%M:%S') + '\n')
            if device.usbstor_datetime65 != datetime.min:
                f.write("USBSTOR Timestamp (65): " + device.usbstor_datetime65.strftime('%Y-%m-%dT%H:%M:%S') + '\n')
            if device.usbstor_datetime66 != datetime.min:
                f.write("USBSTOR Timestamp (66): " + device.usbstor_datetime66.strftime('%Y-%m-%dT%H:%M:%S') + '\n')
            if device.usbstor_datetime67 != datetime.min:
                f.write("USBSTOR Timestamp (67): " + device.usbstor_datetime67.strftime('%Y-%m-%dT%H:%M:%S') + '\n')

            for i in range(len(device.mountpoint2)):
                f.write('MP2 File: ' + device.mountpoint2[i].file + '\n')
                if device.mountpoint2[i].timestamp != datetime.min:
                    f.write('MP2 Timestamp: ' + device.mountpoint2[i].timestamp.strftime('%Y-%m-%dT%H:%M:%S') + '\n')

            for emd in device.emdmgmt:
                f.write('EMD Volume Serial No.: ' + emd.volume_serial_num + '\n')
                f.write('EMD Volume Serial No. (hex): ' + emd.volume_serial_num_hex + '\n')
                f.write('EMD Volume Name: ' + emd.volume_name + '\n')
                if emd.timestamp != datetime.min:
                    f.write('EMD Timestamp: ' + emd.timestamp.strftime('%Y-%m-%dT%H:%M:%S') + '\n')

            f.write('------------------------------------------------------------------------------\n')


def get_os_version(registry):
    """Retrieves the OS version from the registry (SOFTWARE)"""
    global os_version
    key = registry.open('Microsoft\\Windows NT\\CurrentVersion')
    reg_value = get_reg_value(key, 'CurrentVersion')
    if not reg_value is None:
        os_version = reg_value.value()


def process_usb_stor(registry):
    """Processes the Enum\\USBStor registry key"""

    write_debug(data='Method: process_usb_stor')

    ccs = []
    root_key = registry.root()
    for k in root_key.subkeys():
        if 'ControlSet' in k.name():
            ccs.append(k.name())

    for c in ccs:
        key = registry.open(c + '\\Enum\\USBStor')
        for k in key.subkeys():
            parts = k.name().split('&')

            if len(parts) == 0:
                continue

            if parts[0].lower() != 'disk':
                write_debug(data='USBStor key name does not include the "disk" keyword: ' + k.name())
                continue

            for device_sk in k.subkeys():
                usb_device = UsbDevice()

                if len(parts) == 4:
                    usb_device.vendor = parts[1]
                    write_debug(name='Vendor', value=usb_device.vendor)
                    usb_device.product = parts[2]
                    write_debug(name='Product', value=usb_device.product)
                    usb_device.version = parts[3]
                    write_debug(name='Version', value=usb_device.version)

                usb_device.usb_stor_datetime = device_sk.timestamp()
                write_debug(name='USBStor Timestamp', value=usb_device.usb_stor_datetime.strftime('%Y-%m-%dT%H:%M:%S'))

                parts_serial_no = device_sk.name().split('&')
                if len(parts_serial_no) == 2:
                    serial_no = parts_serial_no[0]
                else:
                    serial_no = device_sk.name()

                usb_device.serial_number = serial_no
                write_debug(name='USBStor Serial No.', value=usb_device.serial_number)

                # Attempt to retrieve the "ParentIdPrefix" value, if it doesn't exist then
                # use the serial no/key name which is the "ParentIdPrefix" if it contains "&"
                reg_value = get_reg_value(device_sk, 'ParentIdPrefix')
                if not reg_value is None:
                    usb_device.parent_prefix_id = reg_value.value()
                    write_debug(name='ParentIdPrefix', value=usb_device.parent_prefix_id)
                else:
                    write_debug(data='ParentIDPrefix registry value does not exist')
                    if '&' in device_sk.name():
                        usb_device.parent_prefix_id = device_sk.name()
                        write_debug(name='ParentIdPrefix', value=usb_device.parent_prefix_id)
                    else:
                        write_debug(data='Device name does not contain "&":' + device_sk.name())

                if not does_usb_device_exist(usb_device):
                    write_debug(data='USB device does not exist so adding new object')
                    usb_devices.append(usb_device)
                else:
                    write_debug(data='USB device already exists')



def process_usb_stor_properties(registry):
    """
    Processes the CCS \Enum\USBStor keys, which contain key timestamps for Win7 & Win8

    From: http://www.swiftforensics.com/2013/11/windows-8-new-registry-artifacts-part-1.html

    Win7:
    Driver Assembly Date:	{a8b865dd-2e3d-4094-ad97-e593a70c75d6}\0002
    Install Date:	        {83da6326-97a6-4088-9453-a1923f573b29}\0064
    First Install Date:	{83da6326-97a6-4088-9453-a1923f573b29}\0065

    Win8:
    Last Arrival Date: {83da6326-97a6-4088-9453-a1923f573b29}\0066
    Last Removal Date: {83da6326-97a6-4088-9453-a1923f573b29}\0067
    Firmware Date:	 {540b947e-8b40-45bc-a8a2-6a0b894cbda2}\0011
    """

    write_debug(data='Method: process_usb_stor_properties')

    ccs = []
    root_key = registry.root()
    for k in root_key.subkeys():
        if 'ControlSet' in k.name():
            ccs.append(k.name())

    for c in ccs:
        key = registry.open(c + '\\Enum\\USBStor')
        for k in key.subkeys():
            parts = k.name().split('&')

            if len(parts) == 0:
                continue

            if parts[0].lower() != 'disk':
                write_debug(data='USBStor key name does not include the "disk" keyword: ' + k.name())
                continue

            if len(parts) == 4:
                vendor = parts[1]
                product = parts[2]
                version = parts[3]

            for device_sk in k.subkeys():
                write_debug(name='USBStor Serial No.', value=device_sk.name())
                parts_serial_no = device_sk.name().split('&')
                if len(parts_serial_no) == 2:
                    serial_no = parts_serial_no[0]
                else:
                    serial_no = device_sk.name()

                usb_device = get_usb_device(serial_number=serial_no,
                                            vendor=vendor,
                                            product=product,
                                            version=version)
                if usb_device is None:
                    continue

                for sub_key_device in device_sk.subkeys():
                    if sub_key_device.name().lower() != 'properties':
                        continue

                    key64 = get_key(sub_key_device, r'{83da6326-97a6-4088-9453-a1923f573b29}\00000064\00000000')
                    if key64 is not None:
                        value64 = get_reg_value(key64, 'Data')
                        if value64 is not None:
                            usb_device.usbstor_datetime64 = value64.value()
                            write_debug(name='USBSTOR date/time (64)', value=usb_device.usbstor_datetime64.strftime('%Y-%m-%dT%H:%M:%S'))
                    else:
                        write_debug(data='{83da6326-97a6-4088-9453-a1923f573b29}\\00000064\\00000000 is None')

                    key65 = get_key(sub_key_device, r'{83da6326-97a6-4088-9453-a1923f573b29}\00000065\00000000')
                    if key65 is not None:
                        value65 = get_reg_value(key65, 'Data')
                        if value65 is not None:
                            usb_device.usbstor_datetime65 = value65.value()
                            write_debug(name='USBSTOR date/time (65)', value=usb_device.usbstor_datetime65.strftime('%Y-%m-%dT%H:%M:%S'))
                    else:
                        write_debug(data='{83da6326-97a6-4088-9453-a1923f573b29}\\00000065\\00000000 is None')

                    key64win8 = get_key(sub_key_device, r'{83da6326-97a6-4088-9453-a1923f573b29}\0064')
                    if key64win8 is not None:
                        value64win8 = get_reg_value(key64win8, '(default)')
                        if value64win8 is not None:
                            usb_device.usbstor_datetime64 = value64win8.value()
                            write_debug(name='USBSTOR date/time (64)', value=usb_device.usbstor_datetime64.strftime('%Y-%m-%dT%H:%M:%S'))
                    else:
                        write_debug(data='{83da6326-97a6-4088-9453-a1923f573b29}\\0064 is None')

                    key65win8 = get_key(sub_key_device, r'{83da6326-97a6-4088-9453-a1923f573b29}\0065')
                    if key65win8 is not None:
                        value65win8 = get_reg_value(key65win8, '(default)')
                        if not value65win8 is None:
                            usb_device.usbstor_datetime65 = value65win8.value()
                            write_debug(name='USBSTOR date/time (65)', value=usb_device.usbstor_datetime65.strftime('%Y-%m-%dT%H:%M:%S'))
                    else:
                        write_debug(data='{83da6326-97a6-4088-9453-a1923f573b29}\\0065 is None')

                    key66 = get_key(sub_key_device, r'{83da6326-97a6-4088-9453-a1923f573b29}\0066')
                    if key66 is not None:
                        value66 = get_reg_value(key66, '(default)')
                        if value66 is not None:
                            usb_device.usbstor_datetime66 = value66.value()
                            write_debug(name='USBSTOR date/time (66)', value=usb_device.usbstor_datetime66.strftime('%Y-%m-%dT%H:%M:%S'))
                        else:
                            write_debug(data='{83da6326-97a6-4088-9453-a1923f573b29}\\0066\\(default) is None')
                    else:
                        write_debug(data='{83da6326-97a6-4088-9453-a1923f573b29}\\0066 is None')

                    key67 = get_key(sub_key_device, r'{83da6326-97a6-4088-9453-a1923f573b29}\0067')
                    if key67 is not None:
                        value67 = get_reg_value(key67, '(default)')
                        if value67 is not None:
                            usb_device.usbstor_datetime67 = value67.value()
                            write_debug(name='USBSTOR date/time (67)', value=usb_device.usbstor_datetime67.strftime('%Y-%m-%dT%H:%M:%S'))
                    else:
                        write_debug(data='{83da6326-97a6-4088-9453-a1923f573b29}\\0067 is None')


def process_usb(registry):
    """Processes the CCS \Enum\USB keys"""

    write_debug(data='Method: process_usb')

    ccs = []
    root_key = registry.root()
    for k in root_key.subkeys():
        if 'ControlSet' in k.name():
            ccs.append(k.name())

    for c in ccs:
        key = registry.open(c + '\\Enum\\USB')
        for sub_key in key.subkeys():
            if (not 'vid' in sub_key.name().lower() and
                    not 'pid' in sub_key.name().lower()):
                continue

            # Get the serial number which is the next key
            for serial_key in sub_key.subkeys():
                usb_device = get_usb_device(serial_number=serial_key.name())
                if usb_device is None:
                    continue

                vid_pid = sub_key.name().split('&')
                usb_device.vid = vid_pid[0]
                write_debug(name='VID', value=usb_device.vid)
                usb_device.pid = vid_pid[1]
                write_debug(name='PID', value=usb_device.pid)
                usb_device.vid_pid_datetime = sub_key.timestamp()
                write_debug(name='VID/PID datetime', value=usb_device.vid_pid_datetime.strftime('%Y-%m-%dT%H:%M:%S'))


def process_mounted_devices(registry):
    """Processes the MountedDevices keys"""

    write_debug(data='Method: process_mounted_devices')

    global usb_devices

    reg_key = registry.root().find_key('MountedDevices')
    if reg_key is None:
        write_debug(data='MountedDevices key does not exist')
        return

    for usb_device in usb_devices:
        for reg_value in reg_key.values():
            # Example Data: USBSTOR#Disk&Ven_SanDisk&Prod_Cruzer&Rev_7.01#2444120C4E80D827&
            data = reg_value.value()
            data = remove_non_ascii_characters(data)

            if '\\DosDevices\\' in reg_value.name():
                if len(data) == 12:  # Drive Sig (DWORD) Partition Offset (DWORD DWORD)
                    dos_device = bytearray(data[0:4])
                    usb_device.disk_signature = ''.join('{:02x}'.format(byte) for byte in dos_device)
                    write_debug(name='Disk sig', value=usb_device.disk_signature)

            if len(usb_device.parent_prefix_id) > 0:
                if '\\DosDevices\\' in reg_value.name():
                    if usb_device.parent_prefix_id in str(data):
                        usb_device.drive_letter = reg_value.name().replace('\\DosDevices\\', '')
                        write_debug(name='Drive letter', value=usb_device.drive_letter)

            if '\\Volume{' in reg_value.name():
                if usb_device.parent_prefix_id in data:
                    guid = reg_value.name()[11:]
                    guid = guid[:len(guid)-1]
                    usb_device.guid = guid
                    write_debug(name='GUID', value=usb_device.guid)
                    usb_device.mountpoint = data[4:]
                    write_debug(name='Mountpoint', value=usb_device.mountpoint)

            # If the drive letter is missing from being identified by the
            # ParentPrefixId then try matching the full device string
            if len(usb_device.drive_letter) == 0:
                if '\\DosDevices\\' in reg_value.name():
                    if ('USBSTOR#Disk&' +
                            usb_device.vendor + '&' +
                            usb_device.product + '&' +
                            usb_device.version + '#' +
                            usb_device.serial_number) in data:

                        usb_device.drive_letter = reg_value.name().replace('\\DosDevices\\', '')
                        write_debug(name='Drive letter', value=usb_device.drive_letter)

            # If the GUID is missing from being identified by the
            # ParentPrefixId then try matching the full device string
            if len(usb_device.guid) == 0:
                if '\\Volume{' in reg_value.name():

                    temp = str(('USBSTOR#Disk&' +
                            usb_device.vendor + '&' +
                            usb_device.product + '&' +
                            usb_device.version + '#' +
                            usb_device.serial_number))

                    if temp.lower() in data.lower():
                        guid = reg_value.name()[11:]
                        guid = guid[:len(guid)-1]
                        usb_device.guid = guid

                    write_debug(name='GUID', value=usb_device.guid)
                    usb_device.mountpoint = data[4:]
                    write_debug(name='Mountpoint', value=usb_device.mountpoint)


def process_device_classes(registry):
    """Processes the CCS \Control\DeviceClasses\{53f56307-b6bf-11d0-94f2-00a0c91efb8b keys"""

    write_debug(data='Method: process_device_classes')

    ccs = []
    root_key = registry.root()
    for k in root_key.subkeys():
        if 'ControlSet' in k.name():
            ccs.append(k.name())

    global usb_devices

    # Get the DeviceClasses related information e.g. VID & PID + USB Date/Time
    for usb_device in usb_devices:
        if len(usb_device.mountpoint.strip()) == 0:
            continue

        for c in ccs:
            key = registry.open(c + '\\Control\\DeviceClasses\\{53f56307-b6bf-11d0-94f2-00a0c91efb8b}')
            for sub_key in key.subkeys():
                if usb_device.mountpoint in sub_key.name():
                    usb_device.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b = sub_key.timestamp()
                    write_debug(name='Dev Classes date/time (53f56)',
                                value=usb_device.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b.strftime('%Y-%m-%dT%H:%M:%S'))
                    continue

                if usb_device.serial_number in sub_key.name():
                    usb_device.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b = sub_key.timestamp()
                    write_debug(name='Dev Classes date/time (53f56)',
                                value=usb_device.device_classes_datetime_53f56307b6bf11d094f200a0c91efb8b.strftime('%Y-%m-%dT%H:%M:%S'))
                    continue

            key = registry.open(c + '\\Control\\DeviceClasses\\{10497b1b-ba51-44e5-8318-a65c837b6661}')
            for sub_key in key.subkeys():
                if usb_device.mountpoint in sub_key.name():
                    usb_device.device_classes_datetime_10497b1bba5144e58318a65c837b6661 = sub_key.timestamp()
                    write_debug(name='Dev Classes date/time (10497)',
                                value=usb_device.device_classes_datetime_10497b1bba5144e58318a65c837b6661.strftime('%Y-%m-%dT%H:%M:%S'))
                    continue

                if usb_device.serial_number in sub_key.name():
                    usb_device.device_classes_datetime_10497b1bba5144e58318a65c837b6661 = sub_key.timestamp()
                    write_debug(name='Dev Classes date/time (10497)',
                                value=usb_device.device_classes_datetime_10497b1bba5144e58318a65c837b6661.strftime('%Y-%m-%dT%H:%M:%S'))
                    continue

# Software Hive Methods #######################################################

def process_windows_portable_devices(registry):
    """Processes the Microsoft\Windows Portable Devices\Devices key"""

    write_debug(data='Method: process_windows_portable_devices')

    try:
        key = registry.open('Microsoft\\Windows Portable Devices\\Devices')

        global usb_devices

        # Get the DeviceClasses related information e.g. VID & PID + USB Date/Time
        for sub_key in key.subkeys():
            if not '_##_USBSTOR' in sub_key.name() and not '_??_USBSTOR' in sub_key.name():
                continue

            for usb_device in usb_devices:
                if not usb_device.serial_number in sub_key.name():
                    continue

                friendly_name = get_reg_value(sub_key, 'FriendlyName')
                if len(friendly_name.value()) == 0:
                    write_debug(data='FriendlyName value not defined')
                    continue

                temp = friendly_name.value()

                if '(' in temp:
                    usb_device.drive_letter = temp[temp.index('('):]
                    usb_device.drive_letter = usb_device.drive_letter.replace('(', '')
                    usb_device.drive_letter = usb_device.drive_letter.replace(')', '')
                    usb_device.volume_name = temp[0:temp.index('(')]
                    write_debug(name='Drive letter', value=usb_device.drive_letter)
                    write_debug(name='Volume name', value=usb_device.volume_name)
                elif ':\\' in temp:
                    usb_device.drive_letter = temp
                    write_debug(name='Drive letter', value=usb_device.drive_letter)
                else:
                    usb_device.volume_name = temp
                    write_debug(name='Volume name', value=usb_device.volume_name)

    except Registry.RegistryKeyNotFoundException:
        return


def process_emd_mgmt(registry):
    """Processes SOFTWARE\Microsoft\Windows NT\CurrentVersion\EMDMgmt key"""

    write_debug(data='Method: process_emd_mgmt')

    try:
        key = registry.open('Microsoft\\Windows NT\\CurrentVersion\\EMDMgmt')

        global usb_devices

        for sub_key in key.subkeys():
            if not '_##_USBSTOR#Disk&' in sub_key.name() and not '_??_USBSTOR#Disk&' in sub_key.name():
                continue

            volume_serial_no = ''
            volume_name = ''

            write_debug(data=sub_key.name())
            if not '{53f56307-b6bf-11d0-94f2-00a0c91efb8b}' in sub_key.name().lower():
                write_debug(data='Key name does not contain {53f56307-b6bf-11d0-94f2-00a0c91efb8b}')
                continue

            index = sub_key.name().index('#{53f56307-b6bf-11d0-94f2-00a0c91efb8b}')

            mountpoint = sub_key.name()[0:index + 39]
            mountpoint = mountpoint.replace('_??_', '')
            mountpoint = mountpoint.replace('_##_', '')

            write_debug(name='Mountpoint', value=mountpoint)

            if len(mountpoint) == 0:
                continue

            # Now get the string data that is after the GUID
            data = sub_key.name()[index + 39:]  # 38 is the length of the '{53f56....' string/GUID
            if '_' in data:
                volume_serial_no = data[data.rfind('_') + 1:]
                volume_name = data[0:data.rfind('_')]

            for usb_device in usb_devices:
                if usb_device.mountpoint.lower() != mountpoint.lower():
                    continue

                emdMgmt = EmdMgmt()
                emdMgmt.volume_serial_num = volume_serial_no
                write_debug(name='EMDMgmt serial no.', value=emdMgmt.volume_serial_num)
                emdMgmt.volume_name = volume_name
                write_debug(name='EMDMgmt volume name', value=emdMgmt.volume_name)
                emdMgmt.timestamp = sub_key.timestamp()
                write_debug(name='EMDMgmt date/time', value=emdMgmt.timestamp.strftime('%Y-%m-%dT%H:%M:%S'))

                if len(volume_serial_no) > 0:
                    temp_vsn = int(volume_serial_no)
                    emdMgmt.volume_serial_num_hex = "%x" % temp_vsn
                    write_debug(name='EMDMgmt serial no. (hex)', value=emdMgmt.volume_serial_num_hex)

                usb_device.emdmgmt.append(emdMgmt)

    except Registry.RegistryKeyNotFoundException:
        return

##### NTUSER Hive Methods ############################################################################################

def process_mountpoints2(registry, reg_file_path):
    """Processes the Software\Microsoft\Windows\CurrentVersion\Explorer\MountPoints2 key"""
    try:
        key = registry.open('Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\MountPoints2')

        global usb_devices

        for usb_device in usb_devices:
            # If there is no GUID then we cannot match so just continue
            if len(usb_device.guid) == 0:
                continue

            for sub_key in key.subkeys():
                if '{' + usb_device.guid + '}' != sub_key.name():
                    continue

                mp2 = MountPoint2()
                mp2.file = reg_file_path
                mp2.timestamp = sub_key.timestamp()
                usb_device.mountpoint2.append(mp2)

                write_debug(name='Mountpoint2 file', value=mp2.file)
                write_debug(name='Mountpoint2 date/time', value=mp2.timestamp.strftime('%Y-%m-%dT%H:%M:%S'))

    except Registry.RegistryKeyNotFoundException:
        return


# Log File Methods ############################################################

def process_log_file(file):
    """"""
    regexXp1 = '^\[([0-9]+/[0-9]+/[0-9]+\s[0-9]+:[0-9]+:[0-9]+)\s[0-9]+.[0-9]+\sDriver\sInstall\]'
    regexXp2 = '#-019 .*? ID\(s\): usb\\(.+)'
    regexXp3 = '#I121.*? "(.*)"'
    regexVista1 = '>>> *\[Device Install \(Hardware initiated\) - USBSTOR\\(.+)\]'
    regexVista2 = '>>>\s\sSection\sstart\s([0-9]+/[0-9]+/[0-9]+\s[0-9]+:[0-9]+:[0-9]+\.[0-9]+)'
    regexWin78 = '>>>\s\s\[Device\sInstall\s\(Hardware\sinitiated\) - SWD\\WPDBUSENUM\\_\?\?_USBSTOR#(.*)\]'

    with open(file) as f:
        lines = f.readlines()
    f.close()

    install_times = {}
    index = 0

    while index < len(lines) - 1:
        index += 1
        line = lines[index].strip()

        timestamp = ''
        key = ''

        if os == WindowsVersions.WindowsXP or os == WindowsVersions.WindowsXPx64:
            match = re.search(regexXp1, line, re.I)
            if match:
                timestamp = match.group(1)

            if len(timestamp) == 0:
                continue

            match = re.search(regexXp3, line, re.I)
            if match:
                key = match.group(1)

            if len(key) == 0:
                continue

            if 'USB\\' not in key and 'USBSTOR\\' not in key:
                continue

            if key in install_times is False:
                install_times[key] = timestamp

        elif os == WindowsVersions.WindowsVista:
            if not '>>>  [Device Install (Hardware initiated) - USBSTOR' in line:
                continue

            match = re.search(regexVista1, line, re.I)
            if match:
                key = 'USBSTOR\\' + match.group(1)

            if len(key) == 0:
                continue

            # Get the line below
            index += 1
            line = lines[index].strip()

            match = re.search(regexVista2, line, re.I)
            if match:
                timestamp = match.group(1)

            if len(timestamp) == 0:
                continue

            if key not in install_times:
                install_times[key] = timestamp

        else:
            #'>>>\s\s\[Device\sInstall\s\(Hardware\sinitiated\) - SWD\\WPDBUSENUM\\_\?\?_USBSTOR#(.*)\]'
            if not '>>>  [Device Install (Hardware initiated) - SWD\\WPDBUSENUM\\_??_USBSTOR#' in line:
                continue

            #'>>>\s\s\[Device\sInstall\s\(Hardware\sinitiated\) - SWD\\WPDBUSENUM\\_\?\?_USBSTOR#(.*)\]'
            match = re.match('>>>\s\s\[Device\sInstall\s\(Hardware\sinitiated\) - SWD\\\\WPDBUSENUM\\\\_\?\?_USBSTOR#(.*)\]', line, re.I)
            if match:
                key = 'USBSTOR\\' + match.group(1)

            if len(key) == 0:
                continue

            # Now turn the top value into the bottom value
            # usbstor\disk&ven_frespons&prod_tactical_subject&rev_0.00#00000022928277&0#{53f56307-b6bf-11d0-94f2-00a0c91efb8b}
            # usbstor\disk&ven_frespons&prod_tactical_subject&rev_0.00\00000022928277&0
            key = key.replace("\\", "#")

            # Get the line below
            index += 1
            line = lines[index].strip()

            match = re.search(regexVista2, line, re.I)
            if match:
                timestamp = match.group(1)

            if len(timestamp) == 0:
                continue

            if key not in install_times:
                install_times[key] = timestamp

    # Now update the install date/time for the devices
    for key, timestamp in install_times.iteritems():
        for device in usb_devices:
            if os == WindowsVersions.WindowsXP or os == WindowsVersions.WindowsXPx64:
                if (device.vid.lower() + '&' + device.pid.lower() + "\\" + device.serial_number.lower()) in key.lower():
                    device.install_datetime = datetime.strptime(timestamp, "%Y/%m/%d %H:%M:%S.%f")
                elif (device.vendor.lower() + "&" + device.product.lower() + "&" + device.version.lower() + "\\" + device.serial_number.lower()) in key.lower():
                    #I121 "USBSTOR\DISK&VEN_USB_2.0&PROD_&REV_1100\6&12202299&0
                    device.install_datetime = datetime.strptime(timestamp, "%Y/%m/%d %H:%M:%S.%f")
            else:
                if len(device.mountpoint) == 0:
                    continue

                parts = device.mountpoint.split('#')
                if len(parts) == 4:
                    temp = parts[0] + "#" + parts[1] + "#" + parts[2] + '#{53f56307-b6bf-11d0-94f2-00a0c91efb8b}'

                    if temp.lower() in key.lower():
                        write_debug(data='Matched install log timestamp using mountpoint: ' + key.lower())
                        device.install_datetime = datetime.strptime(timestamp, "%Y/%m/%d %H:%M:%S.%f")
                    else:
                        write_debug(data='Unable to match install log timestamp using mountpoint: ' + key.lower())
                else:
                    print('The mountpoint does not contain 4 delimited (#) parts: ' + device.mountpoint)


# Helper Methods ##############################################################

def load_file(file):
    """Loads a file as a registry hive"""
    try:
        print('Loading file: ' + file)
        registry = Registry.Registry(file)

        return registry
    except Exception:
        return None


def parse_windows_timestamp(qword):
    """see http://integriography.wordpress.com/2010/01/16/using-phython-to-parse-and-present-windows-64-bit-timestamps"""
    return datetime.utcfromtimestamp(float(qword) * 1e-7 - 11644473600)


def does_usb_device_exist(usb_device):
    """Iterates through the module level list of USB device objects and determines if the object already exists"""
    global usb_devices

    for device in usb_devices:
        if (device.serial_number == usb_device.serial_number and
                device.vendor == usb_device.vendor and
                device.product == usb_device.product and
                device.version == usb_device.version and
                device.parent_prefix_id == usb_device.parent_prefix_id):
            return True

    return False


def get_usb_device(serial_no):
    """Iterates through the module level list of USB device objects and returns the object if it exists"""
    global usb_devices

    for device in usb_devices:
        if device.serial_number == serial_no:
            return device

    return None


def get_usb_device(**kwargs):
    """Iterates through the module level list of USB device objects and returns the object if it exists"""
    global usb_devices

    for device in usb_devices:
        if len(kwargs) == 1:
            if device.serial_number == kwargs['serial_number']:
                write_debug(data='Located USB device by serial number')
                return device
        elif len(kwargs) == 4:
            write_debug(data=kwargs['serial_number'] + '#' + kwargs['vendor'] + '#' + kwargs['product'] + '#' + kwargs['version'])
            write_debug(data=device.serial_number + '#' + device.vendor + '#' + device.product + '#' + device.version)
            if (device.serial_number == kwargs['serial_number'] and
                device.vendor == kwargs['vendor'] and
                device.product == kwargs['product'] and
                device.version == kwargs['version']):

                write_debug(data='Located USB device by multi key')

                return device

    if len(kwargs) == 1:
        write_debug(data='Unable to locate USB device by serial number: ' + kwargs['serial_number'])
    else:
        write_debug(data='Unable to locate USB device by serial number, vendor, product, version: ' + kwargs['serial_number'] + '#' + kwargs['vendor'] + '#' + kwargs['product'] + '#' + kwargs['version'])

    return None


def control_set_check(sys_reg):
    """Determine which Current Control Set the system was using"""
    registry = Registry.Registry(sys_reg)
    key = registry.open("Select")
    for v in key.values():
        if v.name() == "Current":
            return v.value()


def get_reg_value(reg_key, value):
    """Helper method to retrieve a specific value"""
    try:
        return reg_key.value(value)
    except:
        return None


def get_key(reg_key, key_name):
     """Helper method to retrieve a specific key"""
     try:
         for sk in reg_key.subkeys():
             print(sk.name())
         return reg_key.find_key(key_name)
     except:
         return None


def write_debug(**kwargs):
    """Simple debug logging"""
    if debug_mode is False:
        return

    if len(kwargs) == 1:
        print(kwargs['data'])
    else:
        print(kwargs['name'] + ': ' + kwargs['value'])


def remove_non_ascii_characters(data):
    """Removes all non ascii characters from a string"""
    return ''.join([i if (ord(i) < 128 and ord(i) > 0) else '' for i in data])


def main():
    """Parse the command line parameters and load the configuration."""
    parser = argparse.ArgumentParser(description='Example: usbdeviceforensics --registry "/case/registryhives" ')
    parser.add_argument('-o', '--output', help='The output file name')
    parser.add_argument('-f', '--format', choices=['csv', 'text'], help='Output format')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug mode, which outputs details VERY verbosely')
    parser.add_argument('-r', '--registry', required=True, help='Path to registry hives')
    args = parser.parse_args()

    if args.debug is True:
        global debug_mode
        debug_mode = True

    if args.format is not None:
        if args.output is None:
            print("The output file has not been supplied")
            return

    process(args.registry, args.output, args.format)

if __name__ == "__main__":
    main()