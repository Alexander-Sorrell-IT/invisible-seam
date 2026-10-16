from pathlib import Path

from invisible_seam.matchers import solidity_matcher as sm
from invisible_seam.models import Claim

_SOL = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Vault {
    address owner;
    uint256 public price;

    function withdraw() public {
        require(msg.sender == owner, "not owner");
        payable(owner).transfer(address(this).balance);
    }

    function pause() public onlyOwner {
        // paused
    }

    function setFee(uint256 f) external restricted {
        fee = f;
    }

    function setPrice(uint256 p) public {
        price = p;
    }

    function getPrice() public view returns (uint256) {
        return price;
    }

    function _grantRole(bytes32 r, address a) internal {
        roles[r][a] = true;
    }

    function _helper() private {
        counter++;
    }
}
"""


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "Vault.sol").write_text(_SOL)
    return tmp_path


def _claim(text, subject):
    return Claim(id="C1", type="doc-code", claim=text,
                 source_file=Path("README.md"), source_line=1, subject=subject)


def test_find_solidity_function(tmp_path):
    found = sm.find_solidity_function("setPrice", _repo(tmp_path))
    assert found is not None
    path, line, body = found
    assert path.name == "Vault.sol" and "price = p" in body


def test_missing_guard_is_conflict(tmp_path):
    # public, state-changing, no modifier, no msg.sender check -> real missing access control
    cand = sm.match_solidity_doc_claim(
        _claim("Only the owner may call setPrice; it reverts otherwise.", "setPrice"), _repo(tmp_path))
    assert cand is not None and cand.conflict is True


def test_require_guard_no_conflict(tmp_path):
    cand = sm.match_solidity_doc_claim(
        _claim("withdraw reverts if the caller is not the owner.", "withdraw"), _repo(tmp_path))
    assert cand is not None and cand.conflict is False


def test_only_modifier_no_conflict(tmp_path):
    cand = sm.match_solidity_doc_claim(
        _claim("Only owner can call pause.", "pause"), _repo(tmp_path))
    assert cand is not None and cand.conflict is False


def test_nonstandard_modifier_counts_as_guard(tmp_path):
    # 'restricted' is a modifier even though it isn't named only* -> guarded, no conflict
    cand = sm.match_solidity_doc_claim(
        _claim("Only an authorized account may call setFee.", "setFee"), _repo(tmp_path))
    assert cand is not None and cand.conflict is False


def test_internal_function_access_claim_not_flagged(tmp_path):
    # internal function: the access boundary is its public caller, not here -> never flag
    assert sm.match_solidity_doc_claim(
        _claim("Only owner may grant roles.", "_grantRole"), _repo(tmp_path)) is None


def test_private_function_not_flagged(tmp_path):
    assert sm.match_solidity_doc_claim(
        _claim("Only authorized code calls _helper.", "_helper"), _repo(tmp_path)) is None


def test_non_guard_claim_not_matched(tmp_path):
    assert sm.match_solidity_doc_claim(
        _claim("setPrice updates the stored price.", "setPrice"), _repo(tmp_path)) is None


def test_unknown_function_not_matched(tmp_path):
    assert sm.match_solidity_doc_claim(
        _claim("mintTokens reverts unless owner.", "mintTokens"), _repo(tmp_path)) is None
