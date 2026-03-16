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
        if (dimensions <= 0) throw new IllegalArgumentException("dimensions must be > 0");
        if (vector != null && vector.size() != dimensions) throw new IllegalArgumentException("vector length must match dimensions");
        this.modelId = modelId;
        this.dimensions = dimensions;
        this.vector = vector;
    }
}
