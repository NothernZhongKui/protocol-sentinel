// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

// Compatibility layer for existing regression tests.
// New consumers should import src/AuthorityProbe.sol directly.

import {
    AuthorityProbe as SentinelAuthorityProbe
} from "../../src/AuthorityProbe.sol";

abstract contract AuthorityProbe is SentinelAuthorityProbe {}
