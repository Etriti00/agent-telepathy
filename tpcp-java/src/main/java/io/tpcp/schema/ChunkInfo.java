package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Chunked-transfer metadata for large payloads. */
public class ChunkInfo {
    @JsonProperty("chunk_index")
    public int chunkIndex;

    @JsonProperty("total_chunks")
    public int totalChunks;

    @JsonProperty("transfer_id")
    public String transferId;

    public ChunkInfo() {}

    public ChunkInfo(int chunkIndex, int totalChunks, String transferId) {
        if (chunkIndex < 0) throw new IllegalArgumentException("chunkIndex must be >= 0");
        if (totalChunks < 1) throw new IllegalArgumentException("totalChunks must be >= 1");
        this.chunkIndex = chunkIndex;
        this.totalChunks = totalChunks;
        this.transferId = transferId;
    }
}
