💬 :term:`FAQ`
=============================

When trying to flash the |Product| with `ESPHome Web <https://web.esphome.io>`_ , I get a spinning ring with "connecting" for a few seconds and then it errors out with "Failed to initialize".
    This is an issue related to `ESPHome Web <https://web.esphome.io>`_ when trying to flash ESP32-S2 modules and (at the moment of writing this guide) is still unsolved. Please check alternative ways (on the :ref:`programming-esphome` programming section) of flashing the |Product|.

After connecting the battery, I don't see the e-paper refresh or any LED on.
    The two LEDs that are on the board (STDBY & CHRG) only indicate the state of the battery while charging (USB-C or solar panel). The way to 
    check if the SmartPlant is alive is pressing the Reset pushbutton and see that the e-paper refreshes correctly. If not, you will need to 
    charge the battery through the USB-C. 

After connecting the battery and the USB power I see the both LED (STDBY & CHRG) on.
    Check the battery connection polarity: red with + and black/blue with -. 
    Since there is no standard relative to the JST connectors polarity, please pay 
    special attention when connecting any battery to the board. 

Can I upload ESPHome directly from the Home Assistance setup running on my Raspberry Pi?
    Yes you can, and actually this is one of the simplest and more effective way to upload ESPHome.

Can I upload firmware through the USB-C?
    Yes, the ESP32-S2 includes a full-speed USB On-The-Go (OTG) interface to enable USB communication.

When I try to compile the given YAML and upload it into the board I get some error messages saying that I miss some files (Audiowide.ttf, icon-map.h, etc). How to fix it?
    Just the configuration YAML file isn’t enough and you might get an error asking for missing items (the fonts and the images). The reason is because
    on the configuration we are asking for some files (the fonts that you want for the digits or the icons and the background image with the plant and the gauges).
    
    Therefore you need to upload into the folder with the configuration YAML file the required files. I strongly suggest to use Visual studio code and just drag and 
    drop the items according to the structure mentioned on the :ref:`programming-esphome` programming section.

How is the time handled in the board? 
    The time is handled by the ESP32 internal RTC to keep the design compact and straightforward. Therefore the deep-sleep timing is not very 
    precise, I have observed a loss of around 1-2 minutes out of every hour, resulting in a deep sleep period that lasts around 58 minutes 
    instead of 60. However, for the kind of application this is not a quite big issue. 

Can I use it if there is no internet connection? 
    Yes, and based on tests I made, actually will improve the battery duration in almost one week. You just need to adjust the config YAML file 
    and remove the Wifi components.

Can Smart Plant be used outdoor in garden? Is it weatherproof? And with the printed enclosure? 
    I strongly recommend you to avoid placing them outdoor in garden, directly under a water hose/ sprinkles zone
    or heavy rain. Instead use them on indoor plant pots (or a covered balcony). 
    Despite I designed a 3d printable enclosure that would prevent most of the dirt particles and certain level of moisture from enter in 
    the electronics area, I cannot warranty fully waterproofness.

    However, one of my first backers embedded his board in resin (being careful to leave the reset pushbutton and the USB-C port accessible). 
    He lost access to changing the LiPo, but in addition to a pretty cool design, he gained UV and water resistance.
    
    Regarding sun exposure, the e-paper display degrades under direct UV light exposure. For this, there are some UV blocking films, 
    but at the moment are not mounted on the e-paper displays I sell with the Smart Plant. However they can be acquired on Amazon and 
    placed over the display.

The illluminance sensor doesn't seem to present the right values. 
    Since the VEML7700 gains can be adjusted via software to optimize the illluminance measurement, please have a look at the `Adafruit's tutorial <https://learn.adafruit.com/adafruit-veml7700/adjusting-for-different-light-levels>`_.

What is battery life on single charge?
    With the ESPHome configuration YAML, (10s working and e-paper update, and 1h on deep sleep mode) the expected battery life is around 40-50 days. 
    If you use it without the WiFi settings even more.

Can I attach a solar panel to extend the battery?
    Yes, there are two unsoldered pins marked as +/- where you can attach a 5V solar pannel of your choice. Just make sure the size is fitting 
    the rear cover's size so you can make two holes for passing the wires and glue it carefully to the surface.
    When placing the SmartPlant in the pot, just make sure the sun exposed area is the solar panel and not the e-ink display.

