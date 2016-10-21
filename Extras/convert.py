#!/usr/bin/python

# Kludgey McKludgeface image and sound converter -- generates PROGMEM
# tables for Arduino sketches from WAV files and common image formats.

import sys
import math
from PIL import Image
from os import path


# FORMATTED HEX OUTPUT FUNCTIONS -------------------------------------------

# Some globals (yeah, I know) used by the outputHex() function
hexLimit   = 0 # Total number of elements in array being printed
hexCounter = 0 # Current array element number, 0 to hexLimit-1
hexDigits  = 0 # Number of digits (after 0x) in array elements
hexColumns = 0 # Max number of elements to output before line wrap
hexColumn  = 0 # Current column number, 0 to hexColumns-1

# Initialize counters, etc. for outputHex() function below
def hexReset(count, columns, digits):
	global hexLimit, hexCounter, hexDigits, hexColumns, hexColumn
	hexLimit   = count
	hexCounter = 0
	hexDigits  = digits
	hexColumns = columns
	hexColumn  = columns

# Write hex digit (with some formatting for C array) to stdout
def outputHex(n):
	global hexLimit, hexCounter, hexDigits, hexColumns, hexColumn
	if hexCounter > 0:
		sys.stdout.write(",")              # Comma-delimit prior item
		if hexColumn < (hexColumns - 1):   # If not last item on line,
			sys.stdout.write(" ")      # append space after comma
	hexColumn += 1                             # Increment column number
	if hexColumn >= hexColumns:                # Max column exceeded?
		sys.stdout.write("\n  ")           # Line wrap, indent
		hexColumn = 0                      # Reset column number
	sys.stdout.write("{0:#0{1}X}".format(n, hexDigits + 2))
	hexCounter += 1                            # Increment item counter
	if hexCounter >= hexLimit: print(" };\n"); # Cap off table


# IMAGE CONVERSION ---------------------------------------------------------

gammaFlag  = 0 # Set to '1' on image load; gamma tables should be printed

def convertImage(filename):
	global gammaFlag
	try:
		im       = Image.open(filename)
		# IMAGE MUST BE 10 PIXELS TALL TO
		# MATCH CIRCUIT PLAYGROUND NEOPIXELS
		assert im.size[1] == 10
		im       = im.convert("RGB")
		pixels   = im.load()
		numWords = im.size[0] * im.size[1]
		prefix   = path.splitext(path.split(filename)[1])[0]
		hexReset(numWords, 9, 4)

		gammaFlag = 1
		sys.stderr.write("Image OK\n")
		sys.stdout.write(
		  "#define %sFPS 30\n\n"
		  "const uint16_t PROGMEM %sPixelData[] = {" %
		  (prefix, prefix))

		# Quantize 24-bit image to 16 bits:
		# RRRRRRRR GGGGGGGG BBBBBBBB -> RRRRRGGGGGGBBBBB
		for x in range(im.size[0]): # Column major
			for y in range(im.size[1]):
				p = pixels[x, y]
				outputHex(((p[0] & 0b11111000) << 8) |
					  ((p[1] & 0b11111100) << 3) |
					  ( p[2] >> 3))
		return 1 # Success
	except AssertionError:
		sys.stderr.write("Image must be 10 pixels tall\n")
	except:
		sys.stderr.write("Not an image file (?)\n")

	return 0 # Fail


# AUDIO CONVERSION ---------------------------------------------------------

# Extract unsigned value from a series of bytes (LSB first)
def uvalue(bytes):
	result = 0
	for i, b in enumerate(bytes):
		result += ord(b) << (i * 8)
	return result

def convertWav(filename):
	try:
		bytes = open(filename, "rb").read()
		assert bytes[0:4] == "RIFF" and bytes[8:16] == "WAVEfmt "

		prefix     = path.splitext(path.split(filename)[1])[0]
		chunksize  = uvalue(bytes[16:20])
		channels   = uvalue(bytes[22:24])
		rate       = uvalue(bytes[24:28])
		bytesPer   = uvalue(bytes[32:34])
		bitsPer    = uvalue(bytes[34:36])
		bytesTotal = uvalue(bytes[chunksize + 24:chunksize + 28])
		samples    = bytesTotal / bytesPer
		index_in   = chunksize + 28

		sys.stderr.write("WAV OK\n")
		sys.stdout.write("#define %sSampleRate %d\n\n"
		  "const uint8_t PROGMEM %sAudioData[] = {" %
		  (prefix, rate, prefix))
		hexReset(samples, 12, 2)

		# Merge channels, convert to 8-bit
		if(bitsPer == 16): div = channels * 256
		else:              div = channels
		for i in range(samples):
			sum = 0
			for c in range(channels):
				if bitsPer == 8:
					sum += ord(bytes[index_in])
					index_in += 1
				elif bitsPer == 16:
					sum += (ord(bytes[index_in]) +
					        ord(bytes[index_in + 1]) << 8)
					index_in += 2
			outputHex(sum / div)

		return 1 # Success
	except AssertionError:
		sys.stderr.write("Not a WAV file\n")
	except:
		sys.stderr.write("Can't open\n")

	return 0 # Fail


# MAIN ---------------------------------------------------------------------

for i, filename in enumerate(sys.argv): # Each argument...
	if i == 0: continue # Skip first argument; is program name

	# Attempt image conversion.  If fails, try WAV conversion on same.
	if convertImage(filename) == 0: convertWav(filename)

# If any images were successfully read, output 5- and 6-bit gamma tables
if gammaFlag:
	hexReset(32, 12, 2)
	sys.stdout.write("const uint8_t PROGMEM gamma5[] = {")
	for i in range(32):
		outputHex(int(math.pow(float(i)/31.0,2.7)*255.0+0.5))
	hexReset(64, 12, 2)
	sys.stdout.write("const uint8_t PROGMEM gamma6[] = {")
	for i in range(64):
		outputHex(int(math.pow(float(i)/63.0,2.7)*255.0+0.5))
