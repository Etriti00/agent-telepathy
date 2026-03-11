import { EventEmitter } from 'events';
import { AgentIdentity } from '../schemas/envelope';
import { LWWMap } from '../memory/crdt';
import { AgentIdentityManager } from '../security/crypto';
export declare class TPCPNode extends EventEmitter {
    identity: AgentIdentity;
    host: string;
    port: number;
    adnsUrl?: string;
    peerRegistry: Map<string, {
        identity: AgentIdentity;
        address: string;
    }>;
    sharedMemory: LWWMap;
    identityManager: AgentIdentityManager;
    private _server?;
    private _adnsWs?;
    constructor(identity: AgentIdentity, host?: string, port?: number, adnsUrl?: string);
    registerPeer(identity: AgentIdentity, address: string): void;
    startListening(): Promise<void>;
    private _connectToADNS;
    private _handleInbound;
    private _routeIntent;
    private _handleStateSync;
    broadcastDiscovery(seedNodes?: string[]): Promise<void>;
}
