// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/utils/Counters.sol";
import "./UserRegistry.sol";

contract LandRegistry is AccessControl, Pausable, ERC721, ERC721URIStorage {
    using Counters for Counters.Counter;
    Counters.Counter private _tokenIds;

    UserRegistry public userRegistry;

    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");
    bytes32 public constant SURVEYOR_ROLE = keccak256("SURVEYOR_ROLE");

    enum ParcelStatus { Pending, Active, Disputed, Locked }

    struct LandParcel {
        string parcelId;          // Off-chain database ID
        uint256 tokenId;          // NFT token ID
        address owner;            // Current owner's wallet address
        string ipfsHash;          // IPFS hash containing parcel documents
        uint256 area;            // Land area in square meters
        ParcelStatus status;      // Current status of the parcel
        uint256 registeredAt;    // Registration timestamp
        uint256 lastModified;    // Last modification timestamp
    }

    mapping(string => LandParcel) public parcels;
    mapping(uint256 => string) public tokenIdToParcelId;

    event ParcelRegistered(
        string parcelId,
        uint256 tokenId,
        address owner,
        string ipfsHash,
        uint256 area,
        uint256 timestamp
    );

    event ParcelTransferred(
        string parcelId,
        uint256 tokenId,
        address from,
        address to,
        uint256 timestamp
    );

    event ParcelStatusChanged(
        string parcelId,
        uint256 tokenId,
        ParcelStatus oldStatus,
        ParcelStatus newStatus,
        uint256 timestamp
    );

    event ParcelDataUpdated(
        string parcelId,
        uint256 tokenId,
        string ipfsHash,
        uint256 area,
        uint256 timestamp
    );

    constructor(address _userRegistryAddress) ERC721("GeoLedger Land NFT", "LAND") {
        userRegistry = UserRegistry(_userRegistryAddress);
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }

    modifier onlyRegistrar() {
        require(
            userRegistry.hasRole(REGISTRAR_ROLE, msg.sender),
            "Caller is not a registrar"
        );
        _;
    }

    modifier onlySurveyor() {
        require(
            userRegistry.hasRole(SURVEYOR_ROLE, msg.sender),
            "Caller is not a surveyor"
        );
        _;
    }

    modifier parcelExists(string memory parcelId) {
        require(bytes(parcels[parcelId].parcelId).length > 0, "Parcel does not exist");
        _;
    }

    function registerParcel(
        string memory parcelId,
        address owner,
        string memory ipfsHash,
        uint256 area,
        string memory metadataURI
    ) public onlyRegistrar whenNotPaused {
        require(bytes(parcelId).length > 0, "Parcel ID required");
        require(owner != address(0), "Invalid owner address");
        require(bytes(ipfsHash).length > 0, "IPFS hash required");
        require(area > 0, "Area must be greater than 0");
        require(bytes(parcels[parcelId].parcelId).length == 0, "Parcel already exists");

        _tokenIds.increment();
        uint256 newTokenId = _tokenIds.current();

        // Mint NFT
        _safeMint(owner, newTokenId);
        _setTokenURI(newTokenId, metadataURI);

        LandParcel memory newParcel = LandParcel({
            parcelId: parcelId,
            tokenId: newTokenId,
            owner: owner,
            ipfsHash: ipfsHash,
            area: area,
            status: ParcelStatus.Pending,  // Start with Pending status
            registeredAt: block.timestamp,
            lastModified: block.timestamp
        });

        parcels[parcelId] = newParcel;
        tokenIdToParcelId[newTokenId] = parcelId;

        emit ParcelRegistered(parcelId, newTokenId, owner, ipfsHash, area, block.timestamp);
    }

    function transferParcel(
        string memory parcelId,
        address newOwner
    ) public parcelExists(parcelId) whenNotPaused {
        LandParcel storage parcel = parcels[parcelId];
        require(parcel.status == ParcelStatus.Active, "Parcel is not active");
        require(parcel.owner == msg.sender, "Not parcel owner");
        require(newOwner != address(0), "Invalid new owner address");

        address oldOwner = parcel.owner;
        parcel.owner = newOwner;
        parcel.lastModified = block.timestamp;

        // Transfer NFT
        _transfer(oldOwner, newOwner, parcel.tokenId);

        emit ParcelTransferred(parcelId, parcel.tokenId, oldOwner, newOwner, block.timestamp);
    }

    function updateParcelStatus(
        string memory parcelId,
        ParcelStatus newStatus
    ) public parcelExists(parcelId) whenNotPaused {
        require(
            hasRole(DEFAULT_ADMIN_ROLE, msg.sender) ||
            userRegistry.hasRole(REGISTRAR_ROLE, msg.sender),
            "Not authorized to update status"
        );

        LandParcel storage parcel = parcels[parcelId];
        ParcelStatus oldStatus = parcel.status;
        require(oldStatus != newStatus, "New status must be different");

        parcel.status = newStatus;
        parcel.lastModified = block.timestamp;

        emit ParcelStatusChanged(parcelId, parcel.tokenId, oldStatus, newStatus, block.timestamp);
    }

    function updateParcelData(
        string memory parcelId,
        string memory newIpfsHash,
        uint256 newArea,
        string memory newMetadataURI
    ) public onlySurveyor parcelExists(parcelId) whenNotPaused {
        require(bytes(newIpfsHash).length > 0, "IPFS hash required");
        require(newArea > 0, "Area must be greater than 0");

        LandParcel storage parcel = parcels[parcelId];
        require(parcel.status == ParcelStatus.Active, "Parcel is not active");

        parcel.ipfsHash = newIpfsHash;
        parcel.area = newArea;
        parcel.lastModified = block.timestamp;

        // Update token URI
        _setTokenURI(parcel.tokenId, newMetadataURI);

        emit ParcelDataUpdated(parcelId, parcel.tokenId, newIpfsHash, newArea, block.timestamp);
    }

    function getParcelByParcelId(string memory parcelId) public view parcelExists(parcelId) returns (
        uint256 tokenId,
        address owner,
        string memory ipfsHash,
        uint256 area,
        ParcelStatus status,
        uint256 registeredAt,
        uint256 lastModified
    ) {
        LandParcel memory parcel = parcels[parcelId];
        return (
            parcel.tokenId,
            parcel.owner,
            parcel.ipfsHash,
            parcel.area,
            parcel.status,
            parcel.registeredAt,
            parcel.lastModified
        );
    }

    function getParcelByTokenId(uint256 tokenId) public view returns (
        string memory parcelId_,
        address owner,
        string memory ipfsHash,
        uint256 area,
        ParcelStatus status,
        uint256 registeredAt,
        uint256 lastModified
    ) {
        string memory parcelId = tokenIdToParcelId[tokenId];
        require(bytes(parcelId).length > 0, "Token ID not found");
        LandParcel memory parcel = parcels[parcelId];
        return (
            parcel.parcelId,
            parcel.owner,
            parcel.ipfsHash,
            parcel.area,
            parcel.status,
            parcel.registeredAt,
            parcel.lastModified
        );
    }

    // Override required functions
    function _burn(uint256 tokenId) internal override(ERC721, ERC721URIStorage) {
        super._burn(tokenId);
    }

    function tokenURI(uint256 tokenId) public view override(ERC721, ERC721URIStorage) returns (string memory) {
        return super.tokenURI(tokenId);
    }

    function supportsInterface(bytes4 interfaceId) public view override(ERC721, ERC721URIStorage, AccessControl) returns (bool) {
        return super.supportsInterface(interfaceId);
    }

    function pause() public onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    function unpause() public onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }
}