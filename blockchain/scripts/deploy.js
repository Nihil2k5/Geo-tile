const hre = require("hardhat");
const fs = require("fs");

const NETWORK_INFO = `
----------------------------------
 List endpoints and services 
----------------------------------
 JSON-RPC HTTP service endpoint           : http://localhost:8545
 JSON-RPC WebSocket service endpoint      : ws://localhost:8546
`;

function printNetworkInfo() {
  console.log(NETWORK_INFO);
}

async function main() {
  printNetworkInfo();
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying contracts with the account:", deployer.address);

  // Deploy UserRegistry
  const UserRegistry = await hre.ethers.getContractFactory("UserRegistry");
  const userRegistry = await UserRegistry.deploy();
  await userRegistry.waitForDeployment();
  console.log("UserRegistry deployed to:", await userRegistry.getAddress());

  // Deploy LandRegistry
  const LandRegistry = await hre.ethers.getContractFactory("LandRegistry");
  const landRegistry = await LandRegistry.deploy(await userRegistry.getAddress());
  await landRegistry.waitForDeployment();
  console.log("LandRegistry deployed to:", await landRegistry.getAddress());

  // Deploy DisputeManager
  const DisputeManager = await hre.ethers.getContractFactory("DisputeManager");
  const disputeManager = await DisputeManager.deploy(
    await userRegistry.getAddress(),
    await landRegistry.getAddress()
  );
  await disputeManager.waitForDeployment();
  console.log("DisputeManager deployed to:", await disputeManager.getAddress());

  // Grant roles
  const REGISTRAR_ROLE = await userRegistry.REGISTRAR_ROLE();
  const COURT_AUTHORITY_ROLE = await userRegistry.COURT_AUTHORITY_ROLE();

  // Grant roles to LandRegistry
  const grantRegistrarTx = await userRegistry.grantRole(REGISTRAR_ROLE, await landRegistry.getAddress());
  await grantRegistrarTx.wait();
  console.log("Granted REGISTRAR_ROLE to LandRegistry");

  // Grant roles to DisputeManager
  const grantCourtTx = await userRegistry.grantRole(COURT_AUTHORITY_ROLE, await disputeManager.getAddress());
  await grantCourtTx.wait();
  console.log("Granted COURT_AUTHORITY_ROLE to DisputeManager");

  // Grant REGISTRAR_ROLE to DisputeManager so it can update parcel statuses
  const grantRegistrarToDisputeTx = await userRegistry.grantRole(REGISTRAR_ROLE, await disputeManager.getAddress());
  await grantRegistrarToDisputeTx.wait();
  console.log("Granted REGISTRAR_ROLE to DisputeManager");

  // Grant REGISTRAR_ROLE to the Django admin address so server-side calls succeed
  const DJANGO_ADMIN = '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266';
  const grantRegistrarToDjangoAdminTx = await userRegistry.grantRole(REGISTRAR_ROLE, DJANGO_ADMIN);
  await grantRegistrarToDjangoAdminTx.wait();
  console.log("Granted REGISTRAR_ROLE to Django admin address", DJANGO_ADMIN);

  // Grant COURT_AUTHORITY_ROLE to deployer for administrative purposes
  const grantCourtToDeployerTx = await userRegistry.grantRole(COURT_AUTHORITY_ROLE, deployer.address);
  await grantCourtToDeployerTx.wait();
  console.log("Granted COURT_AUTHORITY_ROLE to deployer for administrative purposes");

  // Save contract addresses to a file for easy access
  const contractAddresses = {
    UserRegistry: await userRegistry.getAddress(),
    LandRegistry: await landRegistry.getAddress(),
    DisputeManager: await disputeManager.getAddress()
  };

  fs.writeFileSync(
    "contract-addresses.json",
    JSON.stringify(contractAddresses, null, 2)
  );
  console.log("Contract addresses saved to contract-addresses.json");

  // Save ABIs
  const userRegistryArtifact = require("../artifacts/contracts/UserRegistry.sol/UserRegistry.json");
  const landRegistryArtifact = require("../artifacts/contracts/LandRegistry.sol/LandRegistry.json");
  const disputeManagerArtifact = require("../artifacts/contracts/DisputeManager.sol/DisputeManager.json");

  const artifacts = {
    UserRegistry: userRegistryArtifact,
    LandRegistry: landRegistryArtifact,
    DisputeManager: disputeManagerArtifact
  };

  fs.writeFileSync(
    "contract-abis.json",
    JSON.stringify(artifacts, null, 2)
  );
  console.log("Contract ABIs saved to contract-abis.json");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });