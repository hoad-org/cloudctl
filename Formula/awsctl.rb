class Awsctl < Formula
  include Language::Python::Virtualenv

  desc "Enterprise Cloud Identity & Context Manager (AWS, Azure, GCP)"
  homepage "https://github.com/beyondtrust-cloudops/aws-terraform-infra-cloudops-awsctl"
  # -------------------------------------------------------------------------
  # RELEASE CHECKLIST:
  #   1. Push a git tag: git tag v3.0.0 && git push --tags
  #   2. Compute sha256: curl -sL <tarball_url> | shasum -a 256
  #   3. Update url + sha256 below and run: brew audit --strict Formula/awsctl.rb
  # -------------------------------------------------------------------------
  url "https://github.com/beyondtrust-cloudops/aws-terraform-infra-cloudops-awsctl/archive/refs/tags/v3.0.0.tar.gz"
  sha256 "REPLACE_WITH_ACTUAL_SHA256_AFTER_TAGGING"
  license "MIT"
  head "https://github.com/beyondtrust-cloudops/aws-terraform-infra-cloudops-awsctl.git", branch: "main"

  depends_on "python@3.12"

  # Direct runtime dependencies (mirrors pyproject.toml)
  resource "boto3" do
    url "https://files.pythonhosted.org/packages/d9/68/90feb74f486305c703d323308a4759006631b890d9357b6dd11ebf251908/boto3-1.34.0.tar.gz"
    sha256 "c9b400529932ed4652304756528ab235c6730aa5d00cb4d9e4848ce460c82c16"
  end

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/source/P/PyYAML/PyYAML-6.0.1.tar.gz"
    sha256 "bfdf460b1736c775f2ba9f6a92bca30bc2095067b8a9d77876d1fad6cc3b4a43"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/a7/ec/4a7d80728bd429f7c0d4d51245287158a1516315cadbb146012439403a9d/rich-13.7.0.tar.gz"
    sha256 "5cb5123b5cf9ee70584244246816e9114227e0b98ad9176eede6ad54bf5403fa"
  end

  resource "inquirerpy" do
    url "https://files.pythonhosted.org/packages/64/73/7570847b9da026e07053da3bbe2ac7ea6cde6bb2cbd3c7a5a950fa0ae40b/InquirerPy-0.3.4.tar.gz"
    sha256 "89d2ada0111f337483cb41ae31073108b2ec1e618a49d7110b0d7ade89fc197e"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/63/70/2bf7780ad2d390a8d301ad0b550f1581eadbd9a20f896afe06353c2a2913/requests-2.32.3.tar.gz"
    sha256 "55365417734eb18255590a9ff9eb97e9e1da868d4ccd6402399eaf68af20a760"
  end

  resource "py-minisign" do
    url "https://files.pythonhosted.org/packages/00/68/98a555cde13b1532519b06b0e1691621396e472acbf288b3b7ace1aa4cab/py_minisign-0.13.2.tar.gz"
    sha256 "52b7e486649385496d5d103c5c7584ac74f6e002557ef3ad2e0152119d4a2cce"
  end

  # boto3 transitive dependencies (pinned for hermeticity)
  resource "botocore" do
    url "https://files.pythonhosted.org/packages/8c/a6/470755d26325a020ea1a4efa8e0eaef37e13480f938523008ccc03aff3dc/botocore-1.34.0.tar.gz"
    sha256 "711b406de910585395466ca649bceeea87a04300ddf74d9a2e20727c7f27f2f1"
  end

  resource "s3transfer" do
    url "https://files.pythonhosted.org/packages/a0/b5/4c570b08cb85fdcc65037b5229e00412583bb38d974efecb7ec3495f40ba/s3transfer-0.10.0.tar.gz"
    sha256 "d0c8bbf672d5eebbe4e57945e23b972d963f07d82f661cabf678a5c88831595b"
  end

  resource "jmespath" do
    url "https://files.pythonhosted.org/packages/00/2a/e867e8531cf3e36b41201936b7fa7ba7b5702dbef42922193f05c8976cd6/jmespath-1.0.1.tar.gz"
    sha256 "90261b206d6defd58fdd5e85f478bf633a2901798906be2ad389150c5c60edbe"
  end

  # InquirerPy transitive dependencies (pinned for hermeticity)
  resource "pfzy" do
    url "https://files.pythonhosted.org/packages/d9/5a/32b50c077c86bfccc7bed4881c5a2b823518f5450a30e639db5d3711952e/pfzy-0.3.4.tar.gz"
    sha256 "717ea765dd10b63618e7298b2d98efd819e0b30cd5905c9707223dceeb94b3f1"
  end

  resource "prompt-toolkit" do
    url "https://files.pythonhosted.org/packages/2d/4f/feb5e137aff82f7c7f3248267b97451da3644f6cdc218edfe549fb354127/prompt_toolkit-3.0.48.tar.gz"
    sha256 "d6623ab0477a80df74e646bdbc93621143f5caf104206aa29294d53de1a03d90"
  end

  def install
    # Build a self-contained virtualenv in libexec so the formula is hermetic
    # and does not pollute the user's system Python.
    venv = virtualenv_create(libexec/"venv", "python3.12")
    venv.pip_install resources
    venv.pip_install buildpath

    # Shim scripts: forward all args to the virtualenv binaries so `awsctl`
    # resolves to the correct interpreter regardless of PATH order.
    (bin/"awsctl").write_env_script(libexec/"venv/bin/awsctl",
      PATH: "#{libexec}/venv/bin:$PATH")
    (bin/"_awsctl_bin").write_env_script(libexec/"venv/bin/_awsctl_bin",
      PATH: "#{libexec}/venv/bin:$PATH")
  end

  def post_install
    # Install the shell wrapper into the user's detected shell profile.
    # awsctl init --shell-only is non-interactive and safe to run in post_install.
    system bin/"awsctl", "init", "--shell-only"
  rescue => e
    opoo "Shell integration could not be installed automatically: #{e}\n" \
         "Run `awsctl init --shell-only` manually after reloading your shell."
  end

  def caveats
    <<~EOS
      awsctl has been installed.

      To enable the shell wrapper (required for `awsctl switch` to set env vars):
        awsctl init --shell-only

      Then reload your shell:
        source ~/.zshrc    # or ~/.bashrc / ~/.bash_profile

      To configure your first organization:
        awsctl org add

      Or run the full wizard:
        awsctl init
    EOS
  end

  test do
    system bin/"awsctl", "--version"
  end
end
