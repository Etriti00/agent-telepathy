package io.tpcp.schema;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/** Carries semantic state via vector embeddings. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class VectorEmbeddingPayload {
    @JsonProperty("payload_type")
    public String payloadType = "vector_embedding";

    @JsonProperty("model_id")
    public String modelId;

    @JsonProperty("dimensions")
    public int dimensions;

    @JsonProperty("vector")
    public List<Double> vector;

    @JsonProperty("raw_text_fallback")
    public String rawTextFallback;

    public VectorEmbeddingPayload() {}

    public VectorEmbeddingPayload(String modelId, int dimensions, List<Double> vector) {
        this.modelId = modelId;
        this.dimensions = dimensions;
        this.vector = vector;
    }
}
