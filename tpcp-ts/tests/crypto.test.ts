import { AgentIdentityManager } from '../src/security/crypto';

describe('AgentIdentityManager', () => {
  it('should generate a new key pair and sign/verify', () => {
    const manager = new AgentIdentityManager();
    const pubKey = manager.getPublicKeyString();
    
    expect(pubKey).toBeDefined();
    
    const payload = { test: 'value', number: 42 };
    const signature = manager.signPayload(payload);
    
    expect(signature).toBeDefined();
    
    const isValid = AgentIdentityManager.verifySignature(pubKey, signature, payload);
    expect(isValid).toBe(true);
  });
  
  it('should reject invalid signatures', () => {
    const manager1 = new AgentIdentityManager();
    const manager2 = new AgentIdentityManager();
    
    const pubKey1 = manager1.getPublicKeyString();
    const payload = { test: 'value' };
    const signature2 = manager2.signPayload(payload); // Signed by wrong key
    
    const isValid = AgentIdentityManager.verifySignature(pubKey1, signature2, payload);
    expect(isValid).toBe(false);
  });
});
