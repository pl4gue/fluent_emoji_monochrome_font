SHELL := /bin/bash

WEBFONT := fluent-emoji-webfont
DIST := dist

PREPARE := $(WEBFONT)/prepare.py
UPSTREAM_BUILD := $(WEBFONT)/build_ttf.sh

MONO_FONT := $(DIST)/FluentEmojiHighContrastMonochrome.ttf

.PHONY: all init prepare mono color flat hc hc-inv fonts clean distclean \
        update-submodule status

all: mono

mono: $(MONO_FONT)

all: fonts mono

init:
	git submodule update --init --recursive

prepare:
	cd $(WEBFONT) && python prepare.py "High Contrast"

mono: $(MONO_FONT)

$(MONO_FONT): prepare build_mono.py
	mkdir -p $(DIST)
	python build_mono.py

color:
	cd $(WEBFONT) && ./build_ttf.sh color
	cp $(WEBFONT)/build/FluentEmojiColor.ttf $(DIST)/

flat:
	cd $(WEBFONT) && ./build_ttf.sh flat
	cp $(WEBFONT)/build/FluentEmojiFlat.ttf $(DIST)/

hc:
	cd $(WEBFONT) && ./build_ttf.sh hc
	cp $(WEBFONT)/build/FluentEmojiHighContrast.ttf $(DIST)/

hc-inv:
	cd $(WEBFONT) && ./build_ttf.sh hc-inv
	cp $(WEBFONT)/build/FluentEmojiHighContrastInverted.ttf $(DIST)/

fonts: color flat hc hc-inv

clean:
	rm -rf $(DIST)
	rm -rf $(WEBFONT)/build
	find $(WEBFONT) -name '*.rej' -delete

distclean: clean
	rm -rf $(WEBFONT)/venv

update-submodule:
	git submodule update --remote --merge

status:
	git submodule status
