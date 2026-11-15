# Scope and launch gates

Queue item: OpenFeeds. Working identity: Feed Grove; independent checkout, never a folder product in the controller repository.

On 15 November 2026, GitHub repository search `feed-grove in:name` returned eight fuzzy matches and no exact `feed-grove` repository name. A quoted web search returned no exact software match. This is preliminary collision screening, not trademark clearance. Recheck before public naming.

## Migration audience and comparison

Target people who already maintain RSS subscriptions in Feedly and want a portable local reader. Feedly's [official OPML export documentation](https://docs.feedly.com/article/52-how-can-i-export-my-sources-and-feeds-through-opml) points to its web export. Its [import documentation](https://docs.feedly.com/article/51-how-to-import-opml-into-feedly) says OPML transfers feeds, not Boards or Read Later articles. Checked 15 November 2026.

Our migration promise must remain equally precise: subscription URLs and folder paths; no Feedly credentials, saved articles, boards, read states, or AI capabilities. Current parser tests use synthetic fixtures, not an owner's actual Feedly export. Do not claim actual account migration acceptance yet.

## Acceptance path

Export OPML from an existing reader → preview subscriptions and duplicates → import atomically → refresh public RSS/Atom → filter and mark articles → restart with state retained → export OPML and full database backup. Current CLI covers parsing/persistence, not the preview, network, or browser portions.

Network fetching must validate every redirect and actual connection destination, reject credentials/private and reserved IPs, cap response size and time, and avoid ambient proxies/credentials. Localhost fixture access must never become a production bypass. XML and article content are untrusted; display plain text, never fetched HTML as executable DOM.

## Concrete distribution preparation

Prepare a reproducible “move your Feedly subscriptions” guide with a downloadable synthetic OPML and a short real app capture showing import → read → star → export. The primary adoption path is that useful migration walkthrough in the independent repository. Verify compatibility against an actual owner-exported OPML before claiming it. Any external listing/integration needs an individually checked policy and working product; no external submission is currently selected or claimed. No publication, emails or social posts authorized by this plan.
