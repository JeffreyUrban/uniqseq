# Homebrew Formula Automation Setup

This document explains the automated Homebrew formula update system.

## How It Works

When you create a GitHub Release in the main `uniqseq` repository:

1. **Release workflow triggers** (`.github/workflows/update-homebrew.yml`)
   - Extracts version from tag (e.g., `v0.2.0` → `0.2.0`)
   - Sends repository_dispatch event to `homebrew-uniqseq` repo

2. **Homebrew tap receives trigger** (`homebrew-uniqseq/.github/workflows/update-formula.yml`)
   - Waits for PyPI release (up to 10 minutes)
   - Fetches package URL and SHA256 from PyPI
   - Updates `Formula/uniqseq.rb` automatically
   - Creates a Pull Request for review

3. **You review and merge the PR**
   - Check that SHA256 matches PyPI
   - Optionally test locally
   - Merge when ready

4. **Users get the update**
   - `brew upgrade uniqseq` pulls the new version

## Setup Required

### GitHub Token

You need to create a Personal Access Token (PAT) to allow the main repo to trigger the homebrew repo.

#### Creating the Token:

1. Go to: https://github.com/settings/tokens/new
2. **Note**: "Homebrew formula updater"
3. **Expiration**: No expiration (or set to 1 year and renew annually)
4. **Scopes**: Select only:
   - `repo` (Full control of private repositories)
     - This includes `public_repo` for public repositories
5. Click **Generate token**
6. **Copy the token immediately** (you won't see it again)

#### Adding the Token as a Secret:

1. Go to the main uniqseq repo: https://github.com/JeffreyUrban/uniqseq/settings/secrets/actions
2. Click **New repository secret**
3. **Name**: `HOMEBREW_UPDATE_TOKEN`
4. **Secret**: Paste the token you just created
5. Click **Add secret**

## Testing the Workflow

### Dry Run (Without Actually Releasing)

You can manually trigger the homebrew update workflow:

1. Go to: https://github.com/JeffreyUrban/homebrew-uniqseq/actions/workflows/update-formula.yml
2. Click "Run workflow"
3. Enter the version to test (e.g., `0.1.1`)
4. Click "Run workflow"

This will create a test PR without needing a full release.

### Full Release Flow

1. **Prepare release**:
   - Update CHANGELOG.md
   - Commit changes
   - Push to main

2. **Create GitHub Release**:
   - Go to: https://github.com/JeffreyUrban/uniqseq/releases/new
   - Tag: `v0.2.0` (or next version)
   - Title: `v0.2.0`
   - Description: Copy from CHANGELOG.md
   - Click "Publish release"

3. **Automated steps happen**:
   - Release workflow publishes to PyPI
   - Update-homebrew workflow triggers
   - Homebrew tap waits for PyPI
   - PR is created in homebrew-uniqseq

4. **Review and merge**:
   - Check the PR in homebrew-uniqseq
   - Test if desired: `brew install --build-from-source jeffreyurban/uniqseq/uniqseq`
   - Merge the PR

## Workflow Files

### Main Repo (`uniqseq`)
- `.github/workflows/update-homebrew.yml` - Triggers on release, sends dispatch to tap

### Homebrew Tap (`homebrew-uniqseq`)
- `.github/workflows/update-formula.yml` - Receives trigger, updates formula, creates PR

## Troubleshooting

### "Workflow not found" error

The `update-homebrew.yml` workflow references a secret. Make sure:
1. The secret `HOMEBREW_UPDATE_TOKEN` exists in the main repo
2. The token has `repo` scope
3. The token hasn't expired

### "PyPI timeout" error

The workflow waits 10 minutes for PyPI. If your PyPI release is slow:
1. Check that the release actually completed
2. The workflow will fail gracefully with an error message
3. You can manually re-run the workflow once PyPI is ready

### PR not created

Check the Actions tab in homebrew-uniqseq:
1. https://github.com/JeffreyUrban/homebrew-uniqseq/actions
2. Look for failed runs
3. Check the logs for errors

## Manual Fallback

If automation fails, you can always update manually:

```bash
# Get new SHA256
curl -s https://pypi.org/pypi/uniqseq/json | jq -r '.releases["0.2.0"][] | select(.packagetype=="sdist")'

# Edit Formula/uniqseq.rb
# - Update url
# - Update sha256
# - Update version in test

# Test
brew install --build-from-source ./Formula/uniqseq.rb
brew test uniqseq

# Commit and push
git add Formula/uniqseq.rb
git commit -m "chore: Update uniqseq to v0.2.0"
git push
```

## Benefits

✅ **Automated**: Formula updates automatically on release
✅ **Safe**: Creates PR for review, not direct merge
✅ **Verified**: Waits for PyPI confirmation before proceeding
✅ **Traceable**: Clear audit trail via PRs
✅ **No manual SHA256**: Fetched directly from PyPI
