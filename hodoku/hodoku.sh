#!/bin/bash
# MSYS_NO_PATHCONV=1 prevents Git Bash/MSYS from converting /flag arguments
# (like /vp, /o, /bs) into Windows paths before passing them to Java.
# MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd):/data" hodoku "$@"
MSYS_NO_PATHCONV=1 java -Xmx512m \
	-Djava.util.logging.config.file=/dev/null \
	-Dswing.deafultlaf=javax.swing.plaf.metal.MetalLookAndFeel \
	-jar "$(dirname "$0")/hodoku.jar" "$@"

