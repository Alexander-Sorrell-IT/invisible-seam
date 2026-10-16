from pathlib import Path

from invisible_seam.extractors import solidity_extractor as se


def _write(tmp_path, body):
    (tmp_path / "C.sol").write_text(body)
    return tmp_path


def test_natspec_guard_claim_extracted(tmp_path):
    repo = _write(tmp_path, """
contract C {
    /// @notice Sets the price.
    /// @dev Only the owner may call this; reverts otherwise.
    function setPrice(uint256 p) public { price = p; }
}
""")
    claims = se.extract_solidity_claims(repo, start_id=1)
    assert len(claims) == 1
    c = claims[0]
    assert c.subject == "setPrice"
    assert c.type == "doc-code"
    assert "revert" in c.claim.lower() or "owner" in c.claim.lower()


def test_natspec_without_guard_is_skipped(tmp_path):
    repo = _write(tmp_path, """
contract C {
    /// @notice Returns the stored price for display.
    function getPrice() public view returns (uint256) { return price; }
}
""")
    assert se.extract_solidity_claims(repo, start_id=1) == []


def test_function_without_natspec_skipped(tmp_path):
    repo = _write(tmp_path, """
contract C {
    function setPrice(uint256 p) public { price = p; }
}
""")
    assert se.extract_solidity_claims(repo, start_id=1) == []


def test_ids_are_sequential_from_start(tmp_path):
    repo = _write(tmp_path, """
contract C {
    /// @dev Only owner; reverts otherwise.
    function a() public {}
    /// @dev Reverts if paused.
    function b() public {}
}
""")
    claims = se.extract_solidity_claims(repo, start_id=5)
    assert [c.id for c in claims] == ["C005", "C006"]
    assert {c.subject for c in claims} == {"a", "b"}
