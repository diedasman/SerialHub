# MeterSIM Device

## Description

The meter SIM device is based on the ESP32-S3 MCU and integrated on a product by Waveshare: https://www.waveshare.com/wiki/ESP32-S3-LCD-1.47

## Product Description

Wave ESP32-S3 1.47inch Display Dev Board The Wave ESP32-S3 1.47-Inch Display Development Board is a microcontroller platform with a dual-core Xtensa LX7 processor supporting 2.4GHz Wi-Fi and Bluetooth 5 (BLE). It features a vivid 1.47-inch TFT LCD screen for GUI development and includes robust memory, USB connectivity, and flexible GPIO options for rapid prototyping. With onboard 16MB Flash, 8MB PSRAM, and a TF card slot for external storage, the board is ideal for HMI applications. It supports development in both Arduino IDE and ESP-IDF, offering versatility for IoT and low-power projects. 

# Quick Spec

* Processor: Xtensa 32-bit LX7 dual-core, 240MHz 
* Wireless: 2.4GHz Wi-Fi (802.11 b/g/n), Bluetooth 5 (BLE) 
* Memory: 512KB SRAM, 384KB ROM, 16MB Flash, 8MB PSRAM 
* Display: 1.47-inch TFT LCD, 172×320 resolution, 262K colours 
* Controller: ST7789 display controller 
* Interfaces: USB Type-A, TF card slot, GPIO pins 
* Power: Flexible clock and multiple power modes for efficiency 
* RGB Lighting: Integrated RGB LED with acrylic interlayer 
* Dimensions: 36.4 x 20.3mm

## Firmware

Currently a baseline firmware exists that implements some device functionality enabling it for testing the SerialHub app.
Firmware is to be further developed by Codex.

## Scope

### Short term: 

Implement modes for device operation; Basic serial, DLMS meter simulation, TCP, etc. Only implemnt basic serial mode and DLMS as placeholder mode. RGB LED is to change color with each mode. The integrated touch display should be used to provide the user with info and also read touch input to toggle mode. Two buttons should be present on the display; start/stop serial stream and mode toggle/cycle.

### Long term: 

DLMS meter simulation implementation. Device simulated DLMS meter comms.