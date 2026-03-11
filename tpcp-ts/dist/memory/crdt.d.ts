export declare class LWWMap {
    nodeId: string;
    private _state;
    logicalClock: number;
    constructor(nodeId: string);
    set(key: string, value: any, timestamp?: number, writerId?: string): void;
    get(key: string): any;
    merge(otherState: Record<string, {
        value: any;
        timestamp: number;
        writer_id: string;
    }>): void;
    toDict(): Record<string, any>;
    serializeState(): Record<string, {
        value: any;
        timestamp: number;
        writer_id: string;
    }>;
}
