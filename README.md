# supernote-tool

`supernote-tool` is an unofficial python tool for [Ratta Supernote](https://supernote.com).
It allows converting a Supernote's `*.note` file into PNG image file
without operating export function on a real device.

This tool is under development and may change.


## Installation

```
$ pip install supernotelib
```


## Usage

To convert first page of your note into PNG image:

```
$ supernote-tool convert your.note output.png
```

To convert all pages:

```
$ supernote-tool convert -a your.note output.png
```

If you want to specify page number to convert:

```
$ supernote-tool convert -n 3 your.note output.png
```

You can colorize a note by specifing alternative color codes in order of black, darkgray, gray and white.
Note that use `#fefefe` for white because `#ffffff` is used for transparent.

To convert black into red:

```
$ supernote-tool convert -c "#ff0000,#9d9d9d,#c9c9c9,#fefefe" your.note output.png
```

To convert into SVG file format:

```
$ supernote-tool convert -t svg your.note output.svg
```

To convert all pages into PDF file format:

```
$ supernote-tool convert -t pdf -a your.note output.pdf
```

You can also convert your handwriting to vector format and save it as PDF with `--pdf-type vector` option.
Note that converting to a vector takes time.

```
$ supernote-tool convert -t pdf --pdf-type vector -a your.note output.pdf
```

To extract text from a real-time recognition note introduced from Chauvet2.7.21:

```
$ supernote-tool convert -t txt -a your.note output.txt
```

You can specify a page separator string for text conversion:

```
$ supernote-tool convert -t txt -a --text-page-separator='----' your.note output.txt
```

For developers, dump note metadata as JSON format:

```
$ supernote-tool analyze your.note
```


## Supporting files

* `*.note` file created on Supernote A5 (Firmware SN100.B000.432_release)
* `*.note` file created on Supernote A6X (Firmware Chauvet 2.23.36)
* `*.note` file created on Supernote A5X (Firmware Chauvet 2.23.36)
* `*.note` file created on Supernote A6X2 (Firmware Chauvet 3.25.39)
* `*.note` file created on Supernote A5X2 (Firmware Chauvet 3.25.39)

## License

This software is released under the Apache License 2.0, see [LICENSE](LICENSE) file for details.
