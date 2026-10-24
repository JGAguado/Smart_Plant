Programming
===========

Start with the ESPHome example for one Smart Plant. It measures the sensors,
refreshes the display once and sleeps for one hour. You can use the display
without Home Assistant. Home Assistant is optional for viewing readings over
the network.

.. _programming-esphome:

1. Prepare ESPHome
------------------

Use `ESPHome Device Builder in Home Assistant
<https://esphome.io/install/>`_ or the
`ESPHome command-line tools
<https://esphome.io/guides/cli/>`_. You need a
USB data cable and access to the computer that will flash the board.

Download :download:`configuration.yaml <files/configuration.yaml>` into your
ESPHome configuration directory and give your copy a unique filename, such as
``my-plant.yaml``. This example already selects the ESP32-S2 board and its pins.
Keep those hardware settings when adapting it.

2. Configure your plant
-----------------------

Edit these values in your copy:

* ``device_name``: a unique lowercase device name.
* ``friendly_name``: the name shown in sensor labels.
* ``screen_title`` and ``secondary_name``: display-only text.
* ``timezone``: your IANA timezone, such as ``Europe/Paris``.
* ``ap_pwd``: a new password for the fallback Wi-Fi hotspot.

Add your network credentials to the existing ``wifi:`` block. Keep its other
settings. Do not add a second ``wifi:`` block.

.. code-block:: yaml

   wifi:
     ssid: !secret wifi_ssid
     password: !secret wifi_password
     # Keep the example's fast_connect, power_save_mode and ap settings here.

Put the matching values in ``secrets.yaml`` next to your device file:

.. code-block:: yaml

   wifi_ssid: "Your network name"
   wifi_password: "Your network password"

Do not publish your secrets. If adapting an existing device configuration,
preserve its API encryption key and OTA credentials. Configure OTA
authentication for your selected ESPHome version; see the `ESPHome OTA component
<https://esphome.io/components/ota/esphome/>`_.

Use the supplied plant-only illustration for the first test. Follow
:doc:`labels` to configure the text, recommendations and scales in YAML.
Images and Google Fonts are fetched at build time. Local assets permit offline
builds when the required compiler dependencies are already present.

.. Note::
    Invalid sensor readings show ``--``. The device waits for the e-paper
    to finish refreshing. If it does not finish, bounded recovery resets
    the panel before the device requests deep sleep.

.. _flashing:

3. Flash through USB
--------------------

Read :doc:`safety` and :doc:`assembly` first.

.. caution::

   Power the board only through USB while flashing. Disconnect the battery and
   solar input before this step. Check battery polarity before reconnecting it.

Connect Smart Plant to the computer that will perform the serial upload.
Hold **Flash**, press and release **Reset**, then release **Flash** to enter
flashing mode.

In Device Builder, choose **Install** and the serial installation option that
matches where the USB cable is connected. A browser-connected board and a board
connected to the Device Builder host use different upload paths. Follow the
current ESPHome installation prompts.

With the command-line tools, run this from your configuration directory:

.. code-block:: console

   esphome config my-plant.yaml
   esphome run my-plant.yaml

Select the connected serial port when prompted. After the upload completes,
press **Reset** once to start the firmware.

If the port is missing or flashing fails, use :doc:`faq`. There is no need to
assume that every ESP32-S2 is incompatible with browser flashing.

4. Verify the first cycle
-------------------------

Keep the USB serial logs open during the first boot. Check that:

* The device connects to your Wi-Fi network.
* Temperature, humidity, light and soil readings appear in the logs.
* The display refreshes with readings. If a value is missing or implausible,
  inspect the sensor logs before trusting the display.
* The device enters deep sleep after the measurement and display cycle.

The e-paper keeps its last image during sleep. An unchanged screen does not
prove that the device is awake or that its readings are recent.

The standalone example uses the native ESPHome API. If you use Home Assistant,
add the device through its ESPHome integration. The short awake window can make
initial discovery or connection difficult; sleeping devices cannot answer API
requests. Home Assistant may keep the last values when it recognizes
deep-sleep support. Its availability display depends on your integration setup.
For an MQTT transport with retained readings, consider the
`MQTT package example
<https://github.com/JGAguado/Smart_Plant/tree/V2R1/examples/multi-device>`_.
Do not add an MQTT-profile device through the ESPHome integration as well.

5. Calibrate the soil reading
-----------------------------

The example maps two ADC voltages to 0% and 100% with ``calibrate_linear``.
These are starting values, not a universal calibration for every plant or soil.
Observe your probe in representative dry and wet conditions, record the raw
voltage, then adjust the two mapping points. Keep water away from the electronics.
The displayed percentage is a relative calibration, not a laboratory soil-water
measurement.

6. Install later updates
------------------------

The example sleeps between cycles. USB power alone does **not** disable deep
sleep or create a permanent OTA window. Use serial flashing for a reliable
update, or start OTA while the device is awake. Do not change the sleep policy
without considering battery use.

For the MQTT packages, follow the multi-device guide. Do not assume that the
standalone example provides remote commands to keep a sleeping device awake.

Firmware reference
------------------

The complete :download:`example YAML <files/configuration.yaml>` contains the
pin mapping, sensor definitions, display layout and sleep scripts.

The battery gauge uses ESPHome's native ``max17043`` component. The MAX17048
stays powered from the battery and hibernates automatically. Do not add a forced
sleep action without checking model support in your selected ESPHome version.

The standalone example uses a fixed delay after requesting a display update.
The shared packages have their own display-completion handling. Inspect the
configuration you select rather than assuming that all examples have identical
refresh and sleep behavior.

Other programming options
-------------------------

For browser installation, see `ESPHome Web <https://web.esphome.io>`_. Use a
browser that supports Web Serial and a USB data cable.

For Arduino development, start with the official
`Arduino-ESP32 documentation <https://docs.espressif.com/projects/arduino-esp32/en/latest/>`_
and select a target that matches the ESP32-S2. Use the :ref:`pinout` for this
board. An Arduino sketch must implement the sensors, display and sleep behavior;
it does not inherit them from the ESPHome example.

The repository also contains a historical
:download:`offline firmware image <files/smart-areca-v2r1-offline.bin>`.
It does not represent your customized YAML. Build your own configuration when
you need current behavior, your credentials or your own label.
