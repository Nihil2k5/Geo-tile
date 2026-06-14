// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

contract UserRegistry is AccessControl, Pausable {
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");
    bytes32 public constant SURVEYOR_ROLE = keccak256("SURVEYOR_ROLE");
    bytes32 public constant COURT_AUTHORITY_ROLE = keccak256("COURT_AUTHORITY_ROLE");
    bytes32 public constant AUDITOR_ROLE = keccak256("AUDITOR_ROLE");

    struct User {
        string userId;          // Off-chain database ID
        address walletAddress;  // Ethereum wallet address
        bool isActive;         // User account status
        uint256 registeredAt;  // Registration timestamp
        uint256 lastModified;  // Last modification timestamp
    }

    mapping(address => User) public usersByWallet;
    mapping(string => User) public usersById;
    mapping(address => string) public walletToUserId;
    mapping(string => address) public userIdToWallet;

    event UserRegistered(
        string userId,
        address walletAddress,
        uint256 timestamp
    );

    event UserStatusChanged(
        string userId,
        address walletAddress,
        bool isActive,
        uint256 timestamp
    );

    event RoleGranted(
        string userId,
        address walletAddress,
        bytes32 role,
        uint256 timestamp
    );

    event RoleRevoked(
        string userId,
        address walletAddress,
        bytes32 role,
        uint256 timestamp
    );

    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
    }

    modifier userExists(string memory userId) {
        require(bytes(usersById[userId].userId).length > 0, "User does not exist");
        _;
    }

    modifier walletNotRegistered(address wallet) {
        require(bytes(usersByWallet[wallet].userId).length == 0, "Wallet already registered");
        _;
    }

    function registerUser(
        string memory userId,
        address walletAddress
    ) public onlyRole(ADMIN_ROLE) walletNotRegistered(walletAddress) whenNotPaused {
        require(bytes(userId).length > 0, "User ID required");
        require(walletAddress != address(0), "Invalid wallet address");
        require(bytes(usersById[userId].userId).length == 0, "User ID already exists");

        User memory newUser = User({
            userId: userId,
            walletAddress: walletAddress,
            isActive: true,
            registeredAt: block.timestamp,
            lastModified: block.timestamp
        });

        usersByWallet[walletAddress] = newUser;
        usersById[userId] = newUser;
        walletToUserId[walletAddress] = userId;
        userIdToWallet[userId] = walletAddress;

        emit UserRegistered(userId, walletAddress, block.timestamp);
    }

    function deactivateUser(
        string memory userId
    ) public onlyRole(ADMIN_ROLE) userExists(userId) whenNotPaused {
        User storage user = usersById[userId];
        require(user.isActive, "User already inactive");

        user.isActive = false;
        user.lastModified = block.timestamp;
        usersByWallet[user.walletAddress].isActive = false;
        usersByWallet[user.walletAddress].lastModified = block.timestamp;

        emit UserStatusChanged(userId, user.walletAddress, false, block.timestamp);
    }

    function reactivateUser(
        string memory userId
    ) public onlyRole(ADMIN_ROLE) userExists(userId) whenNotPaused {
        User storage user = usersById[userId];
        require(!user.isActive, "User already active");

        user.isActive = true;
        user.lastModified = block.timestamp;
        usersByWallet[user.walletAddress].isActive = true;
        usersByWallet[user.walletAddress].lastModified = block.timestamp;

        emit UserStatusChanged(userId, user.walletAddress, true, block.timestamp);
    }

    function assignRole(
        string memory userId,
        bytes32 role
    ) public onlyRole(ADMIN_ROLE) userExists(userId) whenNotPaused {
        require(role != DEFAULT_ADMIN_ROLE, "Cannot assign DEFAULT_ADMIN_ROLE");
        address userWallet = userIdToWallet[userId];
        require(userWallet != address(0), "User wallet not found");

        _grantRole(role, userWallet);
        emit RoleGranted(userId, userWallet, role, block.timestamp);
    }

    function revokeRole(
        string memory userId,
        bytes32 role
    ) public onlyRole(ADMIN_ROLE) userExists(userId) whenNotPaused {
        require(role != DEFAULT_ADMIN_ROLE, "Cannot revoke DEFAULT_ADMIN_ROLE");
        address userWallet = userIdToWallet[userId];
        require(userWallet != address(0), "User wallet not found");

        _revokeRole(role, userWallet);
        emit RoleRevoked(userId, userWallet, role, block.timestamp);
    }

    function getUserByWallet(address wallet) public view returns (
        string memory userId,
        bool isActive,
        uint256 registeredAt,
        uint256 lastModified
    ) {
        User memory user = usersByWallet[wallet];
        require(bytes(user.userId).length > 0, "User not found");
        return (user.userId, user.isActive, user.registeredAt, user.lastModified);
    }

    function getUserById(string memory userId) public view returns (
        address walletAddress,
        bool isActive,
        uint256 registeredAt,
        uint256 lastModified
    ) {
        User memory user = usersById[userId];
        require(bytes(user.userId).length > 0, "User not found");
        return (user.walletAddress, user.isActive, user.registeredAt, user.lastModified);
    }

    function pause() public onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    function unpause() public onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }
}