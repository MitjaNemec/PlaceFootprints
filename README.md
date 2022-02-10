
# Place Footprints

This plugin will place footprints with the following geometry:

- in a line (Linear)
- in square matrix (Matrix)
- around a circle (Circular)

Apart from the pattern, there are two main ways to use the plugin. The components for placement are selected either by consecutive reference numbers or by the same ID on different hierarchical sheets.

## Basic Use

### Consecutive Reference Numbers
If you want to place the footprints by consecutive reference numbers within a sheet, you have to:

- select a footprint which is first in the sequence to be placed
- run the plugin (`Tools/External Plugins/Place Footprints`)
- select `Reference nr`
- select which parts to place by their reference number
- choose which footprint in the sequence you want to place
- select the arrangement (linear, matrix, circular)
- select place dimension (step in x and y axes in linear and matrix mode and angle step and radius in circular mode)
- run the plugin (click `Ok`)

### Equivalent Parts in Hierarchical Sheets
If you want to place the footprints by same ID across hierarchical sheets of the same level, you have to:

- select a footprint which is first in the sequence to be placed
- run the plugin (`Tools/External Plugins/Place Footprints`)
- select `Sheet nr`
- select the hierarchical level by which the footprints will be placed (in complex hierarchies) from the top box of the window
- choose from which sheets you want the footprints to place from the next box down
- select the arrangement (linear, matrix, circular)
- select place dimension (step in x and y axes in linear and matrixc mode and angle step and radius in circlar mode)
- run the plugin (click `Ok`)

## Visual Examples

### Schematic used in examples
Example of a basic hierarchical schematic

![Hierarchical Schematic](https://raw.githubusercontent.com/MitjaNemec/PlaceFootprints/main/screenshots/place_by_example_schematic.gif)

### Place by Sheet
Example of placing the MOSFET from each sheet in a linear placement

![Place by sheet ID](https://raw.githubusercontent.com/MitjaNemec/PlaceFootprints/main/screenshots/place_by_sheet.gif)

### Place by Reference
Example of placing the LEDs from a single sheet in a circular placement

![Place by reference number](https://raw.githubusercontent.com/MitjaNemec/PlaceFootprints/main/screenshots/place_by_ref.gif)

## Notes

- As seen in the MOSFET example above, you don't need to pick the first item in a pattern but remember that all the other items will be referenced to it. It is usually easier to start by placing the first (lowest numbered / annotated) component first.
- If you have a crash with the plugin, you should find a log file in your KiCad project's folder. Please submit it with any issues you open here.
- There isn't currently an icon for this plugin on the toolbar for the PCB Editor. You need to access it from `Tools/External Plugins/Place Footprints`.


