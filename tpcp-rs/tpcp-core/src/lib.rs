//! # tpcp-core
//!
//! no_std-compatible core types and cryptography for the Telepathy Communication Protocol.
//!
//! Enable the `std` feature (on by default) for full standard library support.

#![cfg_attr(not(feature = "std"), no_std)]

extern crate alloc;

pub mod schema;
pub mod identity;
pub mod lwwmap;

pub use schema::*;
pub use identity::*;
pub use lwwmap::LWWMap;
