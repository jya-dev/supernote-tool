# supernote-tool

`supernote-tool` is an unofficial python tool for [Ratta Supernote](https://supernote.com).
It allows converting a Supernote's `*.note` file into PNG image file
without operating export function on a real device.

This tool is under development and may change.


## Installation

```
$ python -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt
```


## Usage

To convert first page of your note into PNG image:

```
$ python supernote-tool.py convert your.note output.png
```

To convert all pages:

```
$ python supernote-tool.py convert -a your.note output.png
```

If you want to specify page number to convert:

```
$ python supernote-tool.py convert -n 3 your.note output.png
```

You can colorize a note by specifing alternative color codes in order of black, darkgray, gray and white.
Note that use `#fefefe` for white because `#ffffff` is used for transparent.

To convert black into red:

```
$ python supernote-tool.py convert -c "#ff0000,#9d9d9d,#c9c9c9,#fefefe" your.note output.png
```

For developers, dump note metadata as JSON format:

```
$ python supernote-tool.py analyze your.note
```


## Supporting files

* `*.note` file created on Supernote A5 (Firmware SN100.B000.386_release)
* `*.note` file created on Supernote A6 X (Firmware C.133)


## License

This software is released under the Apache License 2.0, see [LICENSE](LICENSE) file for details.
