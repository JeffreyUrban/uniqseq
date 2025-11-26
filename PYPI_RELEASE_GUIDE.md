# PyPI Release Guide for uniqseq v0.1.0

This guide walks you through publishing uniqseq to PyPI for the first time.

## Overview

We'll use **Trusted Publishing** (the modern, secure way) - no API tokens needed!

**Workflow**:
1. You create GitHub Release
2. GitHub Actions builds the package
3. GitHub Actions publishes to PyPI automatically

## Prerequisites Checklist

Before starting:
- [ ] PyPI account created and verified
- [ ] 2FA enabled on PyPI account
- [ ] Trusted publishing configured on PyPI
- [ ] Release workflow enabled (already done ✅)

---

## Step 1: Create PyPI Account (5 minutes)

### 1.1 Register on PyPI

Go to: https://pypi.org/account/register/

- **Username**: (choose your username)
- **Email**: (your email)
- **Password**: (strong password)

Click "Create account" and **verify your email**.

### 1.2 Enable Two-Factor Authentication (Required)

PyPI requires 2FA for publishing new projects.

1. Go to: https://pypi.org/manage/account/
2. Click **"Add 2FA"** under Account Security
3. Choose **"Use an authentication application"**
4. Scan QR code with authenticator app:
   - Google Authenticator (iOS/Android)
   - Authy (iOS/Android/Desktop)
   - 1Password, Bitwarden, etc.
5. Enter 6-digit code to confirm
6. **Save recovery codes** in a safe place!

---

## Step 2: Configure Trusted Publishing (5 minutes)

This is the magic step that allows GitHub Actions to publish without API tokens!

### 2.1 Add Pending Publisher

1. Go to: https://pypi.org/manage/account/publishing/
2. Scroll to **"Add a new pending publisher"**
3. Fill in the form:

```
PyPI Project Name:    uniqseq
Owner:                JeffreyUrban
Repository name:      uniqseq
Workflow name:        release.yml
Environment name:     (leave blank)
```

4. Click **"Add"**

### 2.2 Verify Configuration

You should see a pending publisher entry:

```
uniqseq (pending)
Repository: JeffreyUrban/uniqseq
Workflow: release.yml
Added: 2025-11-26
```

**Important**: This stays "pending" until the first successful publish. After the first release, it becomes active.

---

## Step 3: Create GitHub Release (10 minutes)

Now create the v0.1.0 release on GitHub.

### 3.1 Navigate to Releases

Go to: https://github.com/JeffreyUrban/uniqseq/releases/new

### 3.2 Fill in Release Details

**Choose a tag**:
- Click "Choose a tag"
- Type: `v0.1.0`
- Click "Create new tag: v0.1.0 on publish"

**Release title**:
```
v0.1.0 - Initial Release
```

**Description**:
Copy the entire v0.1.0 section from CHANGELOG.md, **starting from**:

```markdown
**Initial Release** - Production-ready streaming multi-line sequence deduplicator.

uniqseq removes repeated sequences of lines from text streams...
```

(Copy everything through the Acknowledgments section)

**Options**:
- [ ] Set as pre-release (leave unchecked)
- [ ] Set as latest release (check this)

### 3.3 Publish Release

Click **"Publish release"** (green button)

---

## Step 4: Monitor GitHub Actions (5-10 minutes)

After publishing the release, GitHub Actions will automatically start.

### 4.1 Watch the Workflow

1. Go to: https://github.com/JeffreyUrban/uniqseq/actions
2. You'll see a new workflow run: **"Release"**
3. Click on it to watch progress

### 4.2 Workflow Steps

The workflow will:

1. ✅ **Checkout code** with full Git history
2. ✅ **Build package** (creates .tar.gz and .whl)
3. ✅ **Verify version** matches tag (v0.1.0)
4. ✅ **Upload to GitHub** (.tar.gz and .whl as release assets)
5. ✅ **Publish to PyPI** (using trusted publishing)

### 4.3 Expected Timeline

- **Total time**: 2-5 minutes
- **Build**: ~1 minute
- **PyPI upload**: ~30 seconds
- **PyPI indexing**: ~1-2 minutes

### 4.4 If It Fails

**Common issues**:

1. **"Trusted publisher not configured"**
   - Solution: Double-check Step 2.1 - make sure form was filled correctly
   - Project name must be exactly `uniqseq`

2. **"Version already exists"**
   - Solution: PyPI doesn't allow re-uploading the same version
   - You'd need to create v0.1.1

3. **"Version mismatch"**
   - Solution: Something wrong with hatch-vcs
   - Check the build logs

---

## Step 5: Verify Publication (2 minutes)

Once the workflow succeeds:

### 5.1 Check PyPI

Go to: https://pypi.org/project/uniqseq/

You should see:
- ✅ Project page for `uniqseq`
- ✅ Version 0.1.0 listed
- ✅ README displayed
- ✅ Download files (.tar.gz and .whl)

### 5.2 Check GitHub Release

Go to: https://github.com/JeffreyUrban/uniqseq/releases/tag/v0.1.0

You should see:
- ✅ Release notes
- ✅ Assets: `uniqseq-0.1.0.tar.gz` and `uniqseq-0.1.0-py3-none-any.whl`

### 5.3 Test Installation

Test installing from PyPI:

```bash
# In a fresh virtual environment or container
pip install uniqseq

# Verify version
uniqseq --version
# Expected: uniqseq version 0.1.0

# Test basic functionality
echo -e "line1\nline2\nline3\nline1\nline2\nline3" | uniqseq --window-size 3
# Expected: line1\nline2\nline3
```

---

## Post-Release Tasks

### Update CHANGELOG.md

After successful release, the CHANGELOG.md already has:
- ✅ v0.1.0 dated 2025-11-26
- ✅ Unreleased section ready for next changes

### Announce Release (Optional)

Consider announcing on:
- Twitter/X
- Reddit (r/Python, r/commandline)
- Hacker News
- Python Weekly newsletter
- Your blog/website

### Monitor Initial Adoption

Check:
- PyPI download stats: https://pypistats.org/packages/uniqseq
- GitHub Stars/Forks
- Issues opened

---

## Future Releases

For subsequent releases (v0.2.0, v0.3.0, etc.):

1. **Update CHANGELOG.md** with new features/fixes
2. **Create GitHub Release** with new tag (e.g., v0.2.0)
3. **GitHub Actions** automatically publishes to PyPI
4. **That's it!** No more PyPI configuration needed

The trusted publisher is now configured, so all future releases are one-click!

---

## Troubleshooting

### "Package upload failed"

Check:
1. 2FA enabled on PyPI?
2. Trusted publisher configured correctly?
3. Workflow has `id-token: write` permission? (✅ already set)

### "Version number mismatch"

The version should automatically come from the Git tag via hatch-vcs.

Debug:
```bash
# Locally, test version extraction
git checkout v0.1.0
python -m build
pip install dist/*.whl
python -c "import uniqseq; print(uniqseq.__version__)"
# Should print: 0.1.0
```

### "Trusted publisher failed"

Double-check the configuration at:
https://pypi.org/manage/account/publishing/

Must match exactly:
- Repository: `JeffreyUrban/uniqseq`
- Workflow: `release.yml`
- No environment name

---

## Summary

**Time to complete**: ~30 minutes (first time)

**Steps**:
1. ✅ Create PyPI account + enable 2FA
2. ✅ Configure trusted publishing
3. ✅ Create GitHub Release
4. ✅ Monitor workflow
5. ✅ Verify on PyPI

**Future releases**: Just step 3 (create GitHub Release) - everything else is automated!

---

## Resources

- PyPI Trusted Publishing: https://docs.pypi.org/trusted-publishers/
- PyPI Help: https://pypi.org/help/
- GitHub Actions: https://docs.github.com/en/actions
- Packaging Guide: https://packaging.python.org/

---

**Questions?** Check the DEPLOYMENT.md for more details or open an issue on GitHub.
