# GLYPH Codec C Implementation

CC = gcc
CFLAGS = -Wall -Wextra -std=c11 -O2 -I./include
LDFLAGS = -lm

SRC_DIR = src
INCLUDE_DIR = include
BUILD_DIR = build

SRCS = $(SRC_DIR)/glyph.c $(SRC_DIR)/json.c
OBJS = $(BUILD_DIR)/glyph.o $(BUILD_DIR)/json.o

LIB = $(BUILD_DIR)/libglyph.a
TEST = $(BUILD_DIR)/test_glyph

.PHONY: all clean test

all: $(LIB)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c $(INCLUDE_DIR)/glyph.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(LIB): $(OBJS)
	ar rcs $@ $^

$(TEST): test/test_glyph.c $(LIB)
	$(CC) $(CFLAGS) $< -L$(BUILD_DIR) -lglyph $(LDFLAGS) -o $@

test: $(TEST)
	./$(TEST)

clean:
	rm -rf $(BUILD_DIR)
