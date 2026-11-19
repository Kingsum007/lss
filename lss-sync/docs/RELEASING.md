# Preparing a public release

The repository is being prepared as a multi-language research SDK. Local package archives and installation examples do not mean a GitHub repository, npm package, or PyPI project has been published.

## Repository identity and license

Before publication, set the repository owner, author attribution, public project URL, and release contact. Replace every `OWNER` placeholder in installation examples with the actual GitHub account or organization.

The project is licensed under MIT. Copyright (c) 2026 Safi Ullah Mirzai. Include the LICENSE file and preserve its notice in distributed source and packages.

Add a `CITATION.cff` file using the actual author details and the chosen release version. GitHub can then show citation information. For a thesis artifact, a versioned archive through Zenodo can provide a DOI. Do not invent author identifiers, repository URLs, or a DOI. [GitHub citation guidance](https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content)

## Validate the exact release contents

Keep the generic SDK, examples, protocol specification, shared fixtures, tests, and installation documentation together. A release should explain which runtime each package supports: the JavaScript client needs browser persistence/cryptography; the Python client needs its declared Python and `cryptography` versions.

Run the repository's JavaScript, Python, interoperability, and package-install checks. Verify installation from the generated npm archive and Python wheel in clean consumer environments. Check that TypeScript consumers can resolve the included declarations. A passing older demo suite is not a substitute for validating the SDK archives.

Inspect the package file lists. Exclude virtual environments, `node_modules`, private keys, `.env` files, user vaults, SQLite databases, caches, and local process logs. Fixtures use only fixed synthetic values. Include the chosen license and relevant documentation in the distributed packages.

The release notes should identify the measured test results, unsupported features, and any API changes. Benchmark claims need the workload, hardware, repetitions, and link-emulation settings. A short engineering check must not be described as the completed thesis evaluation.

## GitHub installation

The following examples become valid only after the real repository exists and contains the `v0.1.0` tag:

```sh
npm install github:OWNER/lss-sync#v0.1.0
python -m pip install "git+https://github.com/OWNER/lss-sync.git@v0.1.0#subdirectory=python"
```

The root is the JavaScript package; `python/` is the Python package. Pin an immutable release version or commit in dependent projects. The Python Git installation requires Git and may need network access to obtain build requirements and dependencies.

Create a GitHub release for the tested tag and attach the source archive, npm package archive, Python wheel, and concise validation report. A release archive lets developers inspect and install the same files that were tested.

## Registry publication

Publishing to npm or PyPI is optional for GitHub-based use. Before registry publication, verify the desired package names are available, set the actual project URLs and license metadata, and configure maintainer accounts and publishing authentication. Do not remove a private/unpublished guard merely to make a command succeed without checking the release contents.

Use a reviewed release workflow with the least permissions needed. Public publication is a separate action from local building and testing. The maintainer should review the concrete repository, license, package contents, and version before the first public release.

## Scope of the first release

Label the first version as a research preview. It provides the synchronization algorithm, client persistence adapters, and a server receipt-store integration point. It does not provide a complete multi-user application, production hosting, account management, key recovery, or a guarantee of delivery while the process is closed or the network is unavailable.

When adding another language, retain the protocol and shared fixtures. Confirm canonical serialization, digests, encryption/AAD, byte limits, batch-control transitions, and receipt handling across implementations before declaring compatibility. Packaging the same rules in another language improves adoption; scientific contribution still depends on the algorithm's specified behavior and measured evaluation.
