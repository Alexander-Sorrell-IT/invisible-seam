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

    function setPrice(uint256 p) public {
        price = p;
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
    repo = _repo(tmp_path)
    found = sm.find_solidity_function("setPrice", repo)
    assert found is not None
    path, line, body = found
    assert path.name == "Vault.sol" and "price = p" in body


def test_missing_guard_is_conflict(tmp_path):
    repo = _repo(tmp_path)
    # claim asserts setPrice is owner-only, but its body has no require/modifier
    c = _claim("Only the owner may call setPrice; it reverts otherwise.", "setPrice")
    cand = sm.match_solidity_doc_claim(c, repo)
    assert cand is not None and cand.conflict is True


def test_require_guard_no_conflict(tmp_path):
    repo = _repo(tmp_path)
    c = _claim("withdraw reverts if the caller is not the owner.", "withdraw")
    cand = sm.match_solidity_doc_claim(c, repo)
    assert cand is not None and cand.conflict is False


def test_modifier_guard_no_conflict(tmp_path):
    repo = _repo(tmp_path)
    c = _claim("Only owner can call pause.", "pause")
    cand = sm.match_solidity_doc_claim(c, repo)
    assert cand is not None and cand.conflict is False


def test_non_guard_claim_not_matched(tmp_path):
    repo = _repo(tmp_path)
    # no revert/access wording -> not our business, return None (never a false seam)
    c = _claim("setPrice updates the stored price.", "setPrice")
    assert sm.match_solidity_doc_claim(c, repo) is None


def test_unknown_function_not_matched(tmp_path):
    repo = _repo(tmp_path)
    c = _claim("mintTokens reverts unless owner.", "mintTokens")
    assert sm.match_solidity_doc_claim(c, repo) is None
