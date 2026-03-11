export declare class AgentIdentityManager {
    private _privateKey;
    private _publicKey;
    constructor(privateKeyBytes?: Uint8Array);
    getPublicKeyString(): string;
    signPayload(payloadDict: Record<string, any>): string;
    static verifySignature(publicKeyStr: string, signatureStr: string, payloadDict: Record<string, any>): boolean;
}
