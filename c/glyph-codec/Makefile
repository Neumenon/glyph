# GLYPH Codec C Implementation

CC = gcc
CFLAGS = -Wall -Wextra -std=c11 -O2 -I./include
LDFLAGS = -lm

SRC_DIR = src
INCLUDE_DIR = include
BUILD_DIR = build

SRCS = $(SRC_DIR)/glyph.c $(SRC_DIR)/json.c $(SRC_DIR)/decimal128.c $(SRC_DIR)/schema_evolution.c $(SRC_DIR)/stream_validator.c
OBJS = $(BUILD_DIR)/glyph.o $(BUILD_DIR)/json.o $(BUILD_DIR)/decimal128.o $(BUILD_DIR)/schema_evolution.o $(BUILD_DIR)/stream_validator.o

LIB = $(BUILD_DIR)/libglyph.a
TEST = $(BUILD_DIR)/test_glyph

.PHONY: all clean test coverage

all: $(LIB)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/glyph.o: $(SRC_DIR)/glyph.c $(INCLUDE_DIR)/glyph.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/json.o: $(SRC_DIR)/json.c $(INCLUDE_DIR)/glyph.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/decimal128.o: $(SRC_DIR)/decimal128.c $(INCLUDE_DIR)/decimal128.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/schema_evolution.o: $(SRC_DIR)/schema_evolution.c $(INCLUDE_DIR)/schema_evolution.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/stream_validator.o: $(SRC_DIR)/stream_validator.c $(INCLUDE_DIR)/stream_validator.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(LIB): $(OBJS)
	ar rcs $@ $^

$(TEST): test/test_glyph.c $(LIB)
	$(CC) $(CFLAGS) $< -L$(BUILD_DIR) -lglyph $(LDFLAGS) -o $@

test: $(TEST)
	./$(TEST)

coverage: CFLAGS = -Wall -Wextra -std=c11 -O0 -I./include -fprofile-arcs -ftest-coverage
coverage: LDFLAGS += -lgcov
coverage: clean $(TEST)
	./$(TEST)
	@echo ""
	@echo "=== Coverage Report ==="
	@gcov -n $(BUILD_DIR)/*.gcda 2>/dev/null | grep -E "^(File|Lines)" | grep -v test_glyph
	@TOTAL=$$(gcov -n $(BUILD_DIR)/*.gcda 2>/dev/null | grep "Lines executed" | grep -v test_glyph | awk -F'[:%]' '{s+=$$2; n++} END {printf "%.1f", s/n}'); \
	echo ""; echo "Total source coverage: $${TOTAL}%"

clean:
	rm -rf $(BUILD_DIR)
