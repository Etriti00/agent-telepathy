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
        this.chunkIndex = chunkIndex;
        this.totalChunks = totalChunks;
        this.transferId = transferId;
    }
}
