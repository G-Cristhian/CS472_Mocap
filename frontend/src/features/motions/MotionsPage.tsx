import { useState } from 'react'
import { useStudio } from '@/app/StudioProvider'
import { MotionCard } from '@/components/ui/MotionCard'
import { NewMotionDialog } from '@/components/ui/NewMotionDialog'
import { PlusIcon, SearchIcon } from '@/components/ui/Icons'

/** Every motion across all projects. A motion is one skeleton built from 2 to 4 recordings. */
export function MotionsPage() {
  const { motions } = useStudio()
  const [dialog, setDialog] = useState(false)
  const [searchBox, setSearchBox] = useState('');

  const searchText = searchBox.trim(); // removes the space before and after from typed text

  // list of what shows up, matching text with name of a motion from motions list
  // functions like "contains" so if the name includes it somewhere (not only at start)
  // it'll show up!!
  const searchDisplay = searchText
    ? motions.filter((mTake) => mTake.name.toLowerCase().includes(searchText.toLowerCase())): motions;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">Motions</h1>
          <p className="page-sub">Every skeleton you have built, across all projects.</p>
        </div>
        <button className="btn btn-project" onClick={() => setDialog(true)}>
          <PlusIcon />
          New motion
        </button>
      </div>

      <div className = "page-search-bar">
        <label className = "search page-search">
          <SearchIcon />
          <input
            type = "search"
            placeholder = "Type here to find your motion!"
            aria-label = "Search box for motions"
            value = {searchBox}
            onChange = {(input) => setSearchBox(input.target.value)}
            onKeyDown = {(input) => {if (input.key === 'Escape') setSearchBox('')}}
          />
        </label>
      </div>

      {motions.length === 0 ? (
        <div className="no-cards">No motions yet.</div>
      ) : searchDisplay.length === 0 ? (
        <div className = "no-cards">
            <p> No match found for "{searchText}". </p>
            <button
              type = "button"
              className = "btn btn-project"
              style = {{ marginTop: 16 }}
              onClick = {() => setSearchBox('')}>
                Clear search
            </button>
        </div> ) : (
        <div className="grid-cards">
          {searchDisplay.map((motion) => (
            <MotionCard key={motion.id} motion={motion} />
          ))}
        </div>
      )}

      {dialog && <NewMotionDialog onClose={() => setDialog(false)} />}
    </div>
  )
}
