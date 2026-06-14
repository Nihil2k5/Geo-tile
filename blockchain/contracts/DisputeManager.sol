// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/token/ERC721/IERC721.sol";
import "./UserRegistry.sol";
import "./LandRegistry.sol";

contract DisputeManager is AccessControl, Pausable {
    UserRegistry public userRegistry;
    LandRegistry public landRegistry;

    bytes32 public constant COURT_AUTHORITY_ROLE = keccak256("COURT_AUTHORITY_ROLE");
    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");

    enum DisputeStatus { Filed, UnderReview, Resolved, Rejected }

    struct Dispute {
        string disputeId;          // Off-chain database ID
        string parcelId;           // Related land parcel ID
        uint256 tokenId;          // NFT token ID
        address complainant;       // Address of person filing dispute
        string ipfsHash;           // IPFS hash containing dispute documents
        DisputeStatus status;      // Current status of dispute
        string resolution;         // Resolution details (IPFS hash)
        uint256 filedAt;          // Filing timestamp
        uint256 lastModified;      // Last modification timestamp
    }

    mapping(string => Dispute) public disputes;
    mapping(string => string[]) public parcelDisputes;
    mapping(uint256 => string[]) public tokenDisputes;

    event DisputeFiled(
        string disputeId,
        string parcelId,
        uint256 tokenId,
        address complainant,
        string ipfsHash,
        uint256 timestamp
    );

    event DisputeStatusChanged(
        string disputeId,
        DisputeStatus oldStatus,
        DisputeStatus newStatus,
        string resolution,
        uint256 timestamp
    );

    event EvidenceAdded(
        string disputeId,
        string ipfsHash,
        uint256 timestamp
    );

    constructor(address _userRegistryAddress, address _landRegistryAddress) {
        userRegistry = UserRegistry(_userRegistryAddress);
        landRegistry = LandRegistry(_landRegistryAddress);
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }

    modifier onlyCourtAuthority() {
        require(
            userRegistry.hasRole(COURT_AUTHORITY_ROLE, msg.sender),
            "Caller is not a court authority"
        );
        _;
    }

    modifier disputeExists(string memory disputeId) {
        require(bytes(disputes[disputeId].disputeId).length > 0, "Dispute does not exist");
        _;
    }

    function fileDispute(
        string memory disputeId,
        string memory parcelId,
        string memory ipfsHash
    ) public whenNotPaused {
        require(bytes(disputes[disputeId].disputeId).length == 0, "Dispute already exists");
        require(bytes(ipfsHash).length > 0, "IPFS hash required");

        // Get parcel data including token ID
        (uint256 tokenId,,,,,uint256 registeredAt,) = landRegistry.getParcelByParcelId(parcelId);
        require(registeredAt > 0, "Parcel does not exist");

        disputes[disputeId] = Dispute({
            disputeId: disputeId,
            parcelId: parcelId,
            tokenId: tokenId,
            complainant: msg.sender,
            ipfsHash: ipfsHash,
            status: DisputeStatus.Filed,
            resolution: "",
            filedAt: block.timestamp,
            lastModified: block.timestamp
        });

        parcelDisputes[parcelId].push(disputeId);
        tokenDisputes[tokenId].push(disputeId);

        // Update parcel status to Disputed
        landRegistry.updateParcelStatus(parcelId, LandRegistry.ParcelStatus.Disputed);

        emit DisputeFiled(disputeId, parcelId, tokenId, msg.sender, ipfsHash, block.timestamp);
    }

    function updateDisputeStatus(
        string memory disputeId,
        DisputeStatus newStatus,
        string memory resolutionIpfsHash
    ) public onlyCourtAuthority disputeExists(disputeId) whenNotPaused {
        require(newStatus != DisputeStatus.Filed, "Cannot revert to Filed status");
        
        Dispute storage dispute = disputes[disputeId];
        DisputeStatus oldStatus = dispute.status;
        require(oldStatus != newStatus, "New status must be different");

        dispute.status = newStatus;
        if (bytes(resolutionIpfsHash).length > 0) {
            dispute.resolution = resolutionIpfsHash;
        }
        dispute.lastModified = block.timestamp;

        // If dispute is resolved or rejected, update parcel status back to Active
        if (newStatus == DisputeStatus.Resolved || newStatus == DisputeStatus.Rejected) {
            landRegistry.updateParcelStatus(dispute.parcelId, LandRegistry.ParcelStatus.Active);
        }

        emit DisputeStatusChanged(
            disputeId,
            oldStatus,
            newStatus,
            resolutionIpfsHash,
            block.timestamp
        );
    }

    function addEvidence(
        string memory disputeId,
        string memory newIpfsHash
    ) public disputeExists(disputeId) whenNotPaused {
        Dispute storage dispute = disputes[disputeId];
        require(
            msg.sender == dispute.complainant || 
            userRegistry.hasRole(COURT_AUTHORITY_ROLE, msg.sender),
            "Not authorized to add evidence"
        );
        require(dispute.status != DisputeStatus.Resolved && 
                dispute.status != DisputeStatus.Rejected,
                "Dispute is closed"
        );

        dispute.ipfsHash = newIpfsHash;
        dispute.lastModified = block.timestamp;

        emit EvidenceAdded(disputeId, newIpfsHash, block.timestamp);
    }

    function getDisputeById(string memory disputeId) public view disputeExists(disputeId) returns (
        string memory parcelId,
        uint256 tokenId,
        address complainant,
        string memory ipfsHash,
        DisputeStatus status,
        string memory resolution,
        uint256 filedAt,
        uint256 lastModified
    ) {
        Dispute memory dispute = disputes[disputeId];
        return (
            dispute.parcelId,
            dispute.tokenId,
            dispute.complainant,
            dispute.ipfsHash,
            dispute.status,
            dispute.resolution,
            dispute.filedAt,
            dispute.lastModified
        );
    }

    function getDisputesByParcel(string memory parcelId) public view returns (string[] memory) {
        return parcelDisputes[parcelId];
    }

    function getDisputesByToken(uint256 tokenId) public view returns (string[] memory) {
        return tokenDisputes[tokenId];
    }

    function pause() public onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    function unpause() public onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }
}