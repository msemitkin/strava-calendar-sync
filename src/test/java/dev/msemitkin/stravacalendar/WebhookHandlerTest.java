package dev.msemitkin.stravacalendar;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class WebhookHandlerTest {
    @Test void comparesVerifyTokens() {
        assertTrue(WebhookHandler.constantTimeEquals("secret", "secret"));
        assertFalse(WebhookHandler.constantTimeEquals("secret", "other"));
        assertFalse(WebhookHandler.constantTimeEquals("secret", null));
    }
}

