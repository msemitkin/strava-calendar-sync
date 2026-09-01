package dev.msemitkin.stravacalendar;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class GoogleCalendarClientTest {
    @Test void stableEventId() { assertEquals("strava123456789", GoogleCalendarClient.eventId(123456789L)); }
}

