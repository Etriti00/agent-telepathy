import { Intent, PROTOCOL_VERSION, AckInfoSchema, ChunkInfoSchema, TelemetryPayloadSchema } from '../src/schemas/envelope';

describe('Schema v0.4.0', () => {
  test('Intent enum has all 10 values', () => {
    const intents = Object.values(Intent);
    expect(intents).toContain('ACK');
    expect(intents).toContain('NACK');
    expect(intents).toContain('Broadcast');
    expect(intents.length).toBe(10);
  });

  test('PROTOCOL_VERSION is 0.4.0', () => {
    expect(PROTOCOL_VERSION).toBe('0.4.0');
  });

  test('AckInfoSchema parses valid ack_info', () => {
    const result = AckInfoSchema.safeParse({
      acked_message_id: '123e4567-e89b-12d3-a456-426614174000',
    });
    expect(result.success).toBe(true);
  });

  test('AckInfoSchema rejects non-uuid acked_message_id', () => {
    const result = AckInfoSchema.safeParse({ acked_message_id: 'not-a-uuid' });
    expect(result.success).toBe(false);
  });

  test('ChunkInfoSchema parses valid chunk_info', () => {
    const result = ChunkInfoSchema.safeParse({
      chunk_index: 0,
      total_chunks: 3,
      transfer_id: '123e4567-e89b-12d3-a456-426614174000',
    });
    expect(result.success).toBe(true);
  });

  test('ChunkInfoSchema rejects total_chunks less than 1', () => {
    const result = ChunkInfoSchema.safeParse({
      chunk_index: 0,
      total_chunks: 0,
      transfer_id: '123e4567-e89b-12d3-a456-426614174000',
    });
    expect(result.success).toBe(false);
  });

  test('TelemetryPayloadSchema parses valid telemetry payload', () => {
    const result = TelemetryPayloadSchema.safeParse({
      sensor_id: 'sensor-42',
      unit: 'celsius',
      readings: [{ value: 23.5, timestamp_ms: 1700000000000, quality: 'Good' }],
      source_protocol: 'mqtt',
    });
    expect(result.success).toBe(true);
  });

  test('TelemetryPayloadSchema rejects unknown source_protocol', () => {
    const result = TelemetryPayloadSchema.safeParse({
      sensor_id: 'sensor-42',
      unit: 'celsius',
      readings: [{ value: 23.5, timestamp_ms: 1700000000000 }],
      source_protocol: 'zigbee',
    });
    expect(result.success).toBe(false);
  });
});
