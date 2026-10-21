Create your plant label
=======================

Give your Smart Plant a name and illustration with the companion
`Label-maker project <https://github.com/JGAguado/Label-maker>`_.
Its plant generator creates the static background. ESPHome draws the current
measurements and gauge needles over that image.

.. image:: images/programming/Lemon_tree_label_page_1.png
   :alt: Lemon-tree background with four gauges and space for live readings
   :width: 592px

Start with an existing background
---------------------------------

For a first hardware test, you can keep the supplied lemon-tree image. Its
preferred-range arcs may differ from your firmware scales. Before using them
to interpret readings, generate a matching background as described below.
To browse other ready-made labels, see the
`plant examples <https://github.com/JGAguado/Label-maker/tree/main/1_Plants/examples>`_
and their generated ``*_label_page_1.png`` files. Check their gauge ranges
before using them with your configuration.

The display background must be **296 by 128 pixels**. Keep the gauge locations
aligned with the display code. The second generated page is not used by the
standalone example.

Generate one label
------------------

The plant e-paper generator uses **JSON** input. Clone Label-maker, create a
Python virtual environment and install ``numpy`` and ``pycairo`` there.
Pycairo also needs the native Cairo library; follow the
`Pycairo installation instructions <https://pycairo.readthedocs.io/en/latest/getting_started.html>`_
for your operating system.

.. code-block:: console

   git clone https://github.com/JGAguado/Label-maker.git
   cd Label-maker
   python3 -m venv .venv

Activate the environment with the command for your operating system, then run:

.. code-block:: console

   python -m pip install numpy pycairo
   cd 1_Plants

Download :download:`the firmware-matched JSON <files/lemon-tree-label.json>`
and save it as ``examples/Lemon_tree/My_plant.json`` in your Label-maker clone.
This local copy matches the standalone YAML: light uses ``[0, 3775]`` and
humidity uses ``[20, 80]``. Its preferred light region is ``[600, 3775]``,
within the firmware range. Preferred regions are illustrative, not care advice
for your plant. Review them before use.

Generate the background from this local copy:

.. code-block:: console

   python -c "from Plants_epaper import main; main('examples/Lemon_tree/My_plant.json', simulation=False, page=1)"

This writes ``examples/Lemon_tree/My_plant_label_page_1.png``.
Run the generator from ``1_Plants`` because the example's resource paths are
relative to that directory. This command generates only the selected label;
running ``Plants_epaper.py`` directly processes every JSON example.

To personalize the local JSON, edit ``title.value`` and ``subtitle.value``.
Set ``image.path`` to your illustration if needed. Run the command again to
regenerate the background. If you rename the JSON, update the command too;
the output takes the same filename stem.

The JSON selects system fonts. Install its requested font, such as Audiowide,
on the generator computer if you want the same lettering. These system fonts
are separate from the Google Fonts fetched by ESPHome during compilation.

Keep the gauges consistent
--------------------------

The original Label-maker examples do not use the firmware scales for all
gauges. The downloadable JSON above corrects those ranges. If you change it,
compare each JSON
``parameters`` entry with the corresponding gauge drawing code in your YAML.
The standalone firmware currently uses:

.. list-table:: Standalone display layout
   :header-rows: 1

   * - JSON parameter
     - Range in the YAML
     - Position in the JSON
     - Radius
   * - ``moisture``
     - 0 to 100%
     - ``[80, 50]``
     - 22
   * - ``light``
     - 0 to 3775 lx
     - ``[134, 70]``
     - 22
   * - ``temperature``
     - -10 to 50 degrees C
     - ``[188, 50]``
     - 22
   * - ``humidity``
     - 20 to 80%
     - ``[242, 70]``
     - 22

Set each JSON ``abs_range`` to match the YAML range. Keep ``rel_range`` within
that range; it marks the preferred region on the static background and does
not calibrate the sensor. Choose that region for your plant. If you change a
gauge position, radius or range in the background, update the YAML drawing
code to match.

Install your background
-----------------------

Copy the PNG into an ``images`` directory next to your device YAML. In the
existing ``image:`` entry, replace only its ``file`` value:

.. code-block:: yaml

   file: "images/my-plant.png"

Keep ``id: page_1_background`` and the other image settings. The display code
refers to that ID. See the `ESPHome image component
<https://esphome.io/components/image/>`_ if you need a different image source.

Validate and rebuild your device configuration, then install it as described
in :doc:`programming`. Changing a PNG on the build computer does not update a
sleeping device. Compare the displayed needles and values with the background
after the next successful flash and measurement cycle.
