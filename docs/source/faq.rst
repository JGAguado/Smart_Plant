Frequently asked questions
==========================

Flashing and setup
------------------

The serial port is missing or flashing stops at "connecting". What should I check?
    Use a USB data cable, check access to the serial port and close other programs
    that use it. Enter :ref:`flashing` mode again. With ESPHome Web, use a browser
    that supports Web Serial. If that path fails, use Device Builder's host serial
    upload or the ESPHome command-line tools in :doc:`programming`. A failed
    connection alone does not identify a firmware or board fault.

Do I need Home Assistant?
    No. ESPHome can build and flash the firmware from its command-line tools.
    The local display works without Home Assistant. Use Home Assistant if you
    want to collect readings and manage entities there.

Can I flash through USB-C?
    Yes. Follow :ref:`flashing` and use a data cable. Disconnect the battery and
    solar input while flashing, as described in the programming guide.

The build cannot find an image or font. What should I copy?
    Check the exact ``file`` entries in your YAML. The supplied example downloads
    its background and Google Fonts during compilation, so the build computer
    needs internet access. It does not require manually copying ``Audiowide.ttf``
    or ``icon-map.h``. For a local image, keep its path relative to the device
    YAML and make sure that file exists. See :doc:`labels`.

Display and measurements
------------------------

The LEDs are off. Is the device broken?
    The STDBY and CHRG LEDs indicate charging state, not whether the firmware is
    running. An e-paper image also remains visible without power. Check the first
    boot over USB serial and confirm the measurement and sleep cycle. A new board
    needs firmware before it can refresh the screen.

The battery and USB are connected, and both charging LEDs are on. What should I do?
    Disconnect power and check battery connector polarity against the board's
    markings. JST connector polarity is not standardized. Read :doc:`safety`
    before reconnecting the battery.

The screen has not changed. Is it asleep?
    It may be asleep, but the image alone cannot prove that. The firmware normally
    refreshes once per measurement cycle, then sleeps. Check logs or the timestamp
    of a new network reading. The standalone clock shows ``--`` when network
    time was not available. Use sensor logs to investigate invalid readings.

The soil percentage looks wrong. How do I calibrate it?
    The default voltage mapping is a starting point. Use readings from your probe
    in representative dry and wet conditions and adjust ``calibrate_linear``.
    See :doc:`programming`. Changing a gauge's preferred range in Label-maker
    does not change the sensor calibration.

The light value looks wrong. What should I check?
    Check that the enclosure and plant do not cover the light sensor. Compare
    the logged illuminance value with the number on the display. A gauge needle
    can reach its limit while the numeric value continues beyond that range.
    Check the display scale before changing sensor settings.

Why do the gauge needles not match my custom background?
    The background geometry and ranges must match the YAML drawing code. The
    Label-maker and firmware examples differ in some ranges. Follow the layout
    checks in :doc:`labels` before generating your final image.

Connectivity and sleep
----------------------

Why does Home Assistant show the device as unavailable?
    The standalone native-API example sleeps between readings. It cannot answer
    API requests while asleep. Home Assistant can retain the last values when
    it recognizes deep-sleep support; behavior depends on the integration and
    how the device was registered. An MQTT profile can retain its last published
    readings too. Stored readings are not live measurements. Check their age.
    Do not add an MQTT-profile device through the ESPHome integration as well.

Does USB power keep the firmware awake for OTA?
    No. The supplied example still enters deep sleep on USB power. Use serial
    flashing or start OTA during an awake window. Check your selected YAML
    before relying on any remote command to keep the device awake.

Can it work without internet access?
    Local measurements and the display do not need Home Assistant or an internet
    service. However, the example uses network time, and compilation downloads
    fonts and an image. For an offline installation, supply local build assets
    and review the time and network-dependent actions in your configuration.
    Removing only the Wi-Fi block is not a complete offline conversion.

Why does the wake time drift?
    Deep-sleep timing and the awake measurement period affect the interval between
    readings. Do not treat the one-hour sleep setting as a precision clock. Use
    observed timestamps if you need to estimate the next wake.

Battery and placement
---------------------

How long does one charge last?
    It depends on battery capacity and health, Wi-Fi conditions, awake duration,
    measurement frequency, display behavior and temperature. The older guide
    quoted 40-50 days for a cycle of about 10 seconds awake and one hour asleep,
    but that is not a validated guarantee for the current firmware. Measure your
    own setup before planning an unattended installation.

Is Smart Plant waterproof?
    No waterproof rating is provided. Keep the electronics away from rain,
    sprinklers and watering. The printed enclosure does not make the device
    waterproof. Protect the e-paper display from direct UV exposure. See
    :doc:`safety` and :doc:`assembly`.

Can I add a solar panel?
    The board supports an optional solar input. Follow the voltage, size and
    polarity requirements in :doc:`assembly`. Keep the panel exposed to light
    while protecting the display and electronics. Solar input does not guarantee
    that charging will cover your device's consumption.
