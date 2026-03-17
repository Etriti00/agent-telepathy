package io.tpcp;

import io.tpcp.schema.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PayloadValidationTest {

    private static final String VALID_BASE64 = "aGVsbG8="; // "hello"
    private static final String INVALID_BASE64 = "not!valid!base64@@";

    // --- AudioPayload ---

    @Test
    void audioPayloadRejectsNullMimeType() {
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
            () -> new AudioPayload(VALID_BASE64, null));
        assertTrue(ex.getMessage().contains("mimeType must not be null"));
    }

    @Test
    void audioPayloadRejectsInvalidBase64() {
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
            () -> new AudioPayload(INVALID_BASE64, "audio/wav"));
        assertTrue(ex.getMessage().contains("is not valid base64"));
    }

    // --- VideoPayload ---

    @Test
    void videoPayloadRejectsNullMimeType() {
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
            () -> new VideoPayload(VALID_BASE64, null));
        assertTrue(ex.getMessage().contains("mimeType must not be null"));
    }

    @Test
    void videoPayloadRejectsInvalidBase64() {
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
            () -> new VideoPayload(INVALID_BASE64, "video/mp4"));
        assertTrue(ex.getMessage().contains("is not valid base64"));
    }

    // --- ImagePayload ---

    @Test
    void imagePayloadRejectsNullMimeType() {
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
            () -> new ImagePayload(VALID_BASE64, null));
        assertTrue(ex.getMessage().contains("mimeType must not be null"));
    }

    @Test
    void imagePayloadRejectsInvalidBase64() {
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
            () -> new ImagePayload(INVALID_BASE64, "image/png"));
        assertTrue(ex.getMessage().contains("is not valid base64"));
    }

    // --- BinaryPayload ---

    @Test
    void binaryPayloadRejectsNullMimeType() {
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
            () -> new BinaryPayload(VALID_BASE64, null));
        assertTrue(ex.getMessage().contains("mimeType must not be null"));
    }

    @Test
    void binaryPayloadRejectsInvalidBase64() {
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
            () -> new BinaryPayload(INVALID_BASE64, "application/octet-stream"));
        assertTrue(ex.getMessage().contains("is not valid base64"));
    }
}
