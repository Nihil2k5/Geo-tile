require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200
      }
    }
  },
  networks: {
    hardhat: {
      chainId: 1337,
      gasPrice: 0,
      blockGasLimit: 30000000,
      hardfork: "berlin", // Use Berlin hardfork to disable EIP-1559
      accounts: {
        count: 20,
        accountsBalance: "10000000000000000000000" // 10000 ETH per account
      }
    },
    localhost: {
      url: "http://127.0.0.1:8545",
      gasPrice: 0,
      blockGasLimit: 30000000
    }
  }
};